#!/usr/bin/env python3
"""
GMT figure layout verification script using OpenCV.

Performs pixel-level inspection of generated GMT plots:
  1. Colorbar-to-main-frame gap detection
  2. Legend-to-main-plot distance measurement
  3. Legend placement rationality (information density analysis)
  4. Legend internal text/marker overlap detection
  5. Element boundary overflow detection
  6. Annotation overlap detection

Usage:
    python verify_plot.py <image_path> [--output REPORT.md] [--output-dir DIR]
                          [--plan plan.md] [--threshold PIXELS] [--ratio FLOAT]

Dependencies:
    pip install opencv-python-headless numpy Pillow
"""

import argparse
import os
import re
import sys
from pathlib import Path
from datetime import datetime
import numpy as np
from PIL import Image

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    print("Error: opencv-python-headless is required. Install with:")
    print("  pip install opencv-python-headless")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def pil_to_cv2(pil_image):
    """Convert PIL RGB image to OpenCV BGR numpy array."""
    rgb = np.array(pil_image)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def cv2_to_gray(bgr_array):
    """Convert BGR array to grayscale."""
    return cv2.cvtColor(bgr_array, cv2.COLOR_BGR2GRAY)


# ---------------------------------------------------------------------------
# Main verifier class
# ---------------------------------------------------------------------------

class PlotVerifier:
    """Analyze a GMT-generated plot image for layout issues."""

    def __init__(self, image_path, min_gap_px=2, min_gap_ratio=0.005, plan_path=None):
        self.image_path = image_path
        self.plan_path = plan_path
        self.img_pil = Image.open(image_path).convert('RGB')
        self.width, self.height = self.img_pil.size
        self.short_side = min(self.width, self.height)
        self.min_gap = max(min_gap_px, int(self.short_side * min_gap_ratio))

        # OpenCV images (primary representation from now on)
        self.bgr = pil_to_cv2(self.img_pil)          # BGR, uint8
        self.gray = cv2_to_gray(self.bgr)            # grayscale, uint8
        self.rgb_array = np.array(self.img_pil)       # for color analysis (RGB, uint8)

        # Detection results storage
        self.frame_bounds = None       # (x0, y0, x1, y1)
        self.colorbar_bounds = None    # (x0, y0, x1, y1)
        self.colorbar_side = None      # 'right', 'bottom', 'left', 'top'
        self.colorbar_length_ratio = None  # colorbar length / frame dimension
        self.colorbar_aspect = None    # colorbar short/long axis ratio
        self.legend_bounds = None      # (x0, y0, x1, y1)
        self.legend_markers = []       # list of (x0,y0,x1,y1)
        self.legend_text_regions = []  # list of (x0,y0,x1,y1)
        self.info_density_map = None
        self.info_density_map_norm = None

        # Plan-based expectations
        self.plan_info = None          # dict of expected elements from plan.md
        self._parse_plan()

        # Issues storage
        self.failures = []
        self.warnings = []
        self.passes = []

        print(f"Image loaded: {self.width}x{self.height} px")
        print(f"Minimum gap threshold: {self.min_gap} px "
              f"(max of {min_gap_px}px and {min_gap_ratio*100:.1f}% of short side)")

    # -----------------------------------------------------------------------
    # Plan parsing: understand what elements the plan expects
    # -----------------------------------------------------------------------

    def _parse_plan(self):
        """Parse plan.md to determine which elements should be on the figure.

        Uses simple keyword matching to extract expectations about:
        - colorbar (side, orientation hints)
        - legend (presence)
        - scale bar (presence)

        When an element is NOT mentioned in the plan, we conservatively
        skip detection for legend and scale bar (to avoid false positives
        from map features). Colorbar is always detected since it's nearly
        universal in GMT figures.
        """
        self.plan_info = {
            'expects_colorbar': False,
            'expects_legend': False,
            'expects_scale_bar': False,
            'colorbar_side_hint': None,
            'colorbar_orient_hint': None,
        }

        if not self.plan_path:
            # No plan: detect everything (legacy behavior)
            self.plan_info['expects_colorbar'] = True
            self.plan_info['expects_legend'] = True
            self.plan_info['expects_scale_bar'] = True
            return

        plan_path = self.plan_path
        if not os.path.exists(plan_path):
            print(f"  Warning: plan file not found: {plan_path}")
            self.plan_info['expects_colorbar'] = True
            self.plan_info['expects_legend'] = True
            self.plan_info['expects_scale_bar'] = True
            return

        with open(plan_path, 'r', encoding='utf-8') as f:
            text = f.read()

        # --- Colorbar ---
        # GMT plots almost always have a colorbar; look for explicit mention
        if re.search(r'(colorbar|色标|colourbar|颜色条|颜色标)', text, re.IGNORECASE):
            self.plan_info['expects_colorbar'] = True
            # Extract position hint
            if re.search(r'(右侧|右边|right|右下)', text, re.IGNORECASE):
                self.plan_info['colorbar_side_hint'] = 'right'
            elif re.search(r'(左侧|左边|left|左下)', text, re.IGNORECASE):
                self.plan_info['colorbar_side_hint'] = 'left'
            elif re.search(r'(底部|下方|bottom)', text, re.IGNORECASE):
                self.plan_info['colorbar_side_hint'] = 'bottom'
            # Orientation hint
            if re.search(r'(竖直|垂直|vertical)', text, re.IGNORECASE):
                self.plan_info['colorbar_orient_hint'] = 'vertical'
            elif re.search(r'(水平|horizontal)', text, re.IGNORECASE):
                self.plan_info['colorbar_orient_hint'] = 'horizontal'

        # --- Legend ---
        # Only expect a legend if explicitly mentioned in the plan.
        # GMT plans that include legend will use words like "图例", "legend"
        if re.search(r'(legend\b|图例)', text, re.IGNORECASE):
            self.plan_info['expects_legend'] = True

        # --- Scale bar ---
        # Expect scale bar if mentioned and NOT marked optional
        if re.search(r'(比例尺|scale\s*bar|scalebar)', text, re.IGNORECASE):
            if not re.search(r'(比例尺.*可选|可选|optional)', text, re.IGNORECASE):
                self.plan_info['expects_scale_bar'] = True

        print(f"\nPlan expectations from {os.path.basename(plan_path)}:")
        print(f"  Colorbar: {'yes' if self.plan_info['expects_colorbar'] else 'not in plan'}"
              f"{' (' + self.plan_info['colorbar_side_hint'] + ')' if self.plan_info['colorbar_side_hint'] else ''}")
        print(f"  Legend:   {'yes' if self.plan_info['expects_legend'] else 'not in plan'}")
        print(f"  Scale bar: {'yes' if self.plan_info['expects_scale_bar'] else 'not in plan'}")

    # -----------------------------------------------------------------------
    # Step 1: Main plot frame detection
    # -----------------------------------------------------------------------

    def detect_main_frame(self):
        """
        Detect the main plot frame.

        Strategy (multi-pass, from most reliable to fallback):
        1. Content boundary: find where non-background content starts
           (works even when frame lines are thin/anti-aliased)
        2. Hough line detection on Canny edges (for plots without white margins)
        3. Density projection (for complex layouts)
        """
        print("\n[1/6] Detecting main plot frame ...")

        # Pass 1: Content boundary detection
        frame = self._content_boundary_frame()
        if frame:
            fx0, fy0, fx1, fy1 = frame
            fw, fh = fx1 - fx0, fy1 - fy0
            img_area = self.width * self.height
            if 0.10 * img_area < fw * fh < 0.96 * img_area:
                self.frame_bounds = frame
                print(f"  Content-boundary frame: ({fx0},{fy0})-({fx1},{fy1}), "
                      f"size: {fw}x{fh}")
                return
            else:
                print(f"  Content-boundary frame rejected (area ratio: {(fw * fh) / img_area:.2f})")

        # Pass 2: Hough line detection
        edges = cv2.Canny(self.gray, 30, 100)
        min_len = int(self.short_side * 0.12)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=50,
                                minLineLength=min_len, maxLineGap=20)

        h_clusters, v_clusters = [], []
        if lines is not None and len(lines) >= 4:
            h_raw, v_raw = [], []
            for line in lines:
                x0, y0, x1, y1 = line[0]
                angle = abs(np.arctan2(y1 - y0, x1 - x0) * 180 / np.pi)
                if angle < 8 or angle > 172:
                    h_raw.append(((y0 + y1) / 2, min(x0, x1), max(x0, x1)))
                elif 82 < angle < 98:
                    v_raw.append(((x0 + x1) / 2, min(y0, y1), max(y0, y1)))
            h_clusters = self._cluster_lines(h_raw, tolerance=8)
            v_clusters = self._cluster_lines(v_raw, tolerance=8)
            print(f"  Hough: {len(h_clusters)} h-clusters, {len(v_clusters)} v-clusters")

        if len(h_clusters) >= 2 and len(v_clusters) >= 2:
            self._find_largest_frame(h_clusters, v_clusters)
        else:
            # Pass 3: Density projection
            print("  Trying density-based detection ...")
            h_clusters, v_clusters = self._density_based_frame(edges)
            if len(h_clusters) >= 2 and len(v_clusters) >= 2:
                self._find_largest_frame(h_clusters, v_clusters)
            else:
                self._fallback_frame_detection()

        fx0, fy0, fx1, fy1 = self.frame_bounds
        print(f"  Main frame: ({fx0}, {fy0}) -> ({fx1}, {fy1}), "
              f"size: {fx1 - fx0}x{fy1 - fy0} px")

    def _content_boundary_frame(self):
        """
        Detect frame by finding the content boundary.

        GMT plots typically have a white (255) background margin.
        The frame is where non-white content begins. We scan inward
        from each edge row-by-row / col-by-col looking for the first
        row/col where a significant fraction of pixels are non-white.

        This is the most robust method because it doesn't depend on
        edge detection quality — it works even for thin/anti-aliased
        frame lines on white backgrounds.
        """
        h, w = self.gray.shape
        # White threshold: pixels darker than 250 are considered "content"
        WHITE_THRESH = 250
        # A row/col needs at least this fraction of non-white pixels to be content
        CONTENT_FRAC = 0.02  # 2% — a thin frame line on white is ~1-3px / width

        # Search up to 35% of each dimension
        max_search_v = int(h * 0.35)
        max_search_h = int(w * 0.35)

        # Two-tier detection for each edge:
        # A) Line detection: find first row/col with a long continuous run of
        #    non-white pixels (catches thin frame lines, ~1-2px on full width)
        # B) Content detection: find first row/col with >1% non-white pixels
        # Take the outermost (earliest from edge) result.

        def _find_first_row(start, end, step):
            """Find first row with a long non-white run or >1% non-white."""
            for y in range(start, end, step):
                row = self.gray[y, :]
                nw = row < WHITE_THRESH
                # Long continuous run (frame line) — at least 15% of width
                if np.any(np.diff(np.where(np.concatenate(
                        [[False], nw, [False]]))[0])[::2] >= w * 0.15):
                    return y
                if np.mean(nw) >= 0.01:
                    return y
            return None

        def _find_first_col(start, end, step):
            """Find first column with a long non-white run or >1% non-white."""
            for x in range(start, end, step):
                col = self.gray[:, x]
                nw = col < WHITE_THRESH
                if np.any(np.diff(np.where(np.concatenate(
                        [[False], nw, [False]]))[0])[::2] >= h * 0.15):
                    return x
                if np.mean(nw) >= 0.01:
                    return x
            return None

        top = _find_first_row(0, max_search_v, 1)
        bottom = _find_first_row(h - 1, h - max_search_v - 1, -1)
        left = _find_first_col(0, max_search_h, 1)
        right = _find_first_col(w - 1, w - max_search_h - 1, -1)

        if (top is not None and bottom is not None and
            left is not None and right is not None and
            top < bottom and left < right):
            return (left, top, right, bottom)
        return None

    def _cluster_lines(self, lines, tolerance=8):
        """Cluster nearby parallel lines by position."""
        if not lines:
            return []
        sorted_lines = sorted(lines, key=lambda l: l[0])
        clusters = [[sorted_lines[0]]]
        for line in sorted_lines[1:]:
            if abs(line[0] - clusters[-1][-1][0]) <= tolerance:
                clusters[-1].append(line)
            else:
                clusters.append([line])
        return [(np.median([l[0] for l in c]), min(l[1] for l in c), max(l[2] for l in c))
                for c in clusters]

    def _find_largest_frame(self, h_clusters, v_clusters):
        """Find the best frame rectangle from line clusters.

        Prefers rectangles near image edges (GMT frames are at the periphery),
        then selects the one with the best combined score (area × edge proximity).
        """
        candidates = []
        h_sorted = sorted(h_clusters, key=lambda l: l[0])
        v_sorted = sorted(v_clusters, key=lambda l: l[0])

        for i, top in enumerate(h_sorted[:-1]):
            for bottom in h_sorted[i + 1:]:
                for j, left in enumerate(v_sorted[:-1]):
                    for right in v_sorted[j + 1:]:
                        if (left[1] - 5 < top[0] < left[2] + 5 and
                            left[1] - 5 < bottom[0] < left[2] + 5 and
                            right[1] - 5 < top[0] < right[2] + 5 and
                            right[1] - 5 < bottom[0] < right[2] + 5):
                            x0, y0 = int(left[0]), int(top[0])
                            x1, y1 = int(right[0]), int(bottom[0])
                            area = (x1 - x0) * (y1 - y0)
                            # Edge proximity: lower = closer to image edge (preferred)
                            edge_dist = (x0 + (self.width - 1 - x1) +
                                         y0 + (self.height - 1 - y1))
                            edge_score = 1.0 / (1.0 + edge_dist / 100.0)
                            score = area * edge_score
                            candidates.append((score, (x0, y0, x1, y1)))

        img_area = self.width * self.height

        if candidates:
            candidates.sort(key=lambda c: c[0], reverse=True)
            best_bounds = candidates[0][1]
            fw = best_bounds[2] - best_bounds[0]
            fh = best_bounds[3] - best_bounds[1]

            if 0.15 * img_area < fw * fh < 0.95 * img_area:
                self.frame_bounds = best_bounds
                return

        margin_x = int(self.width * 0.05)
        margin_y = int(self.height * 0.05)
        self.frame_bounds = (margin_x, margin_y,
                             self.width - margin_x - 1, self.height - margin_y - 1)

    def _density_based_frame(self, edges):
        """Density projection: frame borders are peaks in edge row/col sums."""
        h, w = edges.shape
        h_proj = np.sum(edges > 0, axis=1).astype(np.float64)
        v_proj = np.sum(edges > 0, axis=0).astype(np.float64)

        ks = max(3, self.short_side // 50) | 1  # odd
        kernel = np.ones(ks) / ks
        h_smooth = np.convolve(h_proj, kernel, mode='same')
        v_smooth = np.convolve(v_proj, kernel, mode='same')

        h_thresh = np.mean(h_smooth) + 0.5 * np.std(h_smooth)
        v_thresh = np.mean(v_smooth) + 0.5 * np.std(v_smooth)

        h_peaks = np.where(h_smooth > h_thresh)[0]
        v_peaks = np.where(v_smooth > v_thresh)[0]

        h_groups = self._group_values(h_peaks, gap=30)
        v_groups = self._group_values(v_peaks, gap=30)

        h_clusters = [(np.mean(g), 0, w - 1) for g in h_groups if len(g) >= 2]
        v_clusters = [(np.mean(g), 0, h - 1) for g in v_groups if len(g) >= 2]

        if len(h_clusters) < 2 and len(h_peaks) > 0:
            h_clusters = [(np.percentile(h_peaks, 5), 0, w - 1),
                          (np.percentile(h_peaks, 95), 0, w - 1)]
        if len(v_clusters) < 2 and len(v_peaks) > 0:
            v_clusters = [(np.percentile(v_peaks, 5), 0, h - 1),
                          (np.percentile(v_peaks, 95), 0, h - 1)]

        print(f"  Density-based: {len(h_clusters)} h-clusters, {len(v_clusters)} v-clusters")
        return h_clusters, v_clusters

    def _group_values(self, values, gap=30):
        """Group sorted values by gap threshold."""
        if len(values) == 0:
            return []
        sv = np.sort(values)
        groups, cur = [], [sv[0]]
        for v in sv[1:]:
            if v - cur[-1] <= gap:
                cur.append(v)
            else:
                groups.append(cur)
                cur = [v]
        groups.append(cur)
        return groups

    def _fallback_frame_detection(self):
        """Fallback: conservative margins based on edge content region."""
        edges = cv2.Canny(self.gray, 30, 100)
        rows = np.any(edges > 0, axis=1)
        cols = np.any(edges > 0, axis=0)
        if np.any(rows) and np.any(cols):
            ri, ci = np.where(rows)[0], np.where(cols)[0]
            self.frame_bounds = (ci[0], ri[0], ci[-1], ri[-1])
        else:
            m = int(self.short_side * 0.05)
            self.frame_bounds = (m, m, self.width - m - 1, self.height - m - 1)

    # -----------------------------------------------------------------------
    # Step 2: Colorbar detection
    # -----------------------------------------------------------------------

    def detect_colorbar(self):
        """
        Detect colorbar relative to the main frame.

        Uses gradient magnitude analysis — a colorbar has strong, consistent
        gradient along its long axis (color transitions) and low gradient
        across its short axis.

        Plan-guided: if the plan specifies a side, that side is searched first
        and given a confidence boost.
        """
        print("\n[2/6] Detecting colorbar ...")
        fx0, fy0, fx1, fy1 = self.frame_bounds

        # Order search regions: plan-hinted side first, then others
        regions = [
            ('right',  (fx1, fy0, self.width, fy1)),
            ('bottom', (fx0, fy1, fx1, self.height)),
            ('left',   (0, fy0, fx0, fy1)),
        ]
        if self.plan_info and self.plan_info.get('colorbar_side_hint') == 'left':
            regions = [r for r in regions if r[0] == 'left'] + [r for r in regions if r[0] != 'left']
        elif self.plan_info and self.plan_info.get('colorbar_side_hint') == 'bottom':
            regions = [r for r in regions if r[0] == 'bottom'] + [r for r in regions if r[0] != 'bottom']
        candidates = []
        for side, (rx0, ry0, rx1, ry1) in regions:
            if rx1 - rx0 > 10 and ry1 - ry0 > 10:
                r = self._search_colorbar_region(side, rx0, ry0, rx1, ry1)
                if r:
                    candidates.append(r)

        if candidates:
            best = max(candidates, key=lambda c: c['confidence'])
            if best['confidence'] < 0.30:
                print(f"  Colorbar candidate rejected (low confidence: {best['confidence']:.2f})")
                self._search_colorbar_fallback()
                return
            self.colorbar_bounds = best['bounds']
            self.colorbar_side = best['side']
            cb = self.colorbar_bounds
            print(f"  Colorbar on {best['side']}: ({cb[0]},{cb[1]})-({cb[2]},{cb[3]}), "
                  f"conf={best['confidence']:.2f}")
        else:
            print("  No colorbar detected by gradient method, trying fallback...")
            self._search_colorbar_fallback()

    def _search_colorbar_fallback(self):
        """Fallback colorbar detection using color progression analysis.

        A true colorbar has smooth, monotonic color progression along its long
        axis and near-uniform color along its short axis. This method looks for
        such patterns by analyzing per-column/per-row mean colors.
        """
        fx0, fy0, fx1, fy1 = self.frame_bounds
        fw, fh = fx1 - fx0, fy1 - fy0

        MAX_SHORT_RATIO = 0.08  # Max 8% of frame dimension for colorbar short axis

        candidates = []

        # Search bottom region outside frame (most common for missed colorbars)
        bottom_margin = int(fh * 0.12)
        for ry0 in [fy1, fy1 - bottom_margin // 4]:
            ry1_ = min(ry0 + int(fh * 0.10), self.height)
            if ry1_ - ry0 < 8:
                continue
            region = self.bgr[ry0:ry1_, fx0:fx1]
            rh, rw = region.shape[:2]
            if rh < 5 or rw < 20:
                continue

            # For each row, compute the color progression smoothness along x
            # A colorbar has smooth gradient: neighboring columns should have
            # similar colors, with gradual change from left to right
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY).astype(np.float64)

            # Per-row: check if color changes smoothly along x
            # Use per-column mean as the gradient signal
            col_means = np.mean(gray, axis=0)
            if col_means.max() - col_means.min() < 15:
                continue  # Not enough color variation for a colorbar

            # Smoothness check: gradient of col_means should have consistent sign
            # (monotonic progression) with small local variations
            col_grad = np.diff(col_means)
            if len(col_grad) < 5:
                continue
            # A colorbar has mostly same-sign gradient (monotonic)
            pos_fraction = max(np.mean(col_grad > 0), np.mean(col_grad < 0))
            if pos_fraction < 0.55:
                continue  # Not monotonic enough

            # Per-column variation within the colorbar should be low (uniform short axis)
            row_stds = np.std(gray, axis=1)
            mean_std = np.mean(row_stds)
            if mean_std > 15:
                continue  # Too much variation along short axis

            # Find the active columns (where color is changing)
            abs_grad = np.abs(col_grad)
            if abs_grad.max() > 0:
                abs_grad = abs_grad / abs_grad.max()
            active = np.where(abs_grad > 0.05)[0]
            if len(active) < 10:
                continue
            cb_x0 = fx0 + active[0]
            cb_x1 = fx0 + active[-1] + 2

            cb_w, cb_h = cb_x1 - cb_x0, rh
            if cb_w < 20 or cb_h < 4:
                continue
            if cb_h / max(fh, 1) > MAX_SHORT_RATIO:
                continue

            bar_long = cb_w
            frame_dim = fw
            length_ratio = bar_long / max(frame_dim, 1)
            self.colorbar_length_ratio = length_ratio
            self.colorbar_aspect = cb_h / max(cb_w, 1)

            conf = 0.55 if 0.25 <= length_ratio <= 1.05 else 0.35
            candidates.append({
                'bounds': (cb_x0, ry0, cb_x1, ry1_),
                'side': 'bottom',
                'confidence': conf,
            })

        if candidates:
            best = max(candidates, key=lambda c: c['confidence'])
            if best['confidence'] >= 0.25:
                self.colorbar_bounds = best['bounds']
                self.colorbar_side = best['side']
                cb = self.colorbar_bounds
                print(f"  Colorbar (fallback) on {best['side']}: ({cb[0]},{cb[1]})-({cb[2]},{cb[3]}), "
                      f"conf={best['confidence']:.2f}")
                return

        print("  No colorbar detected (fallback also failed)")
        self.colorbar_side = None

    def _search_colorbar_region(self, side, rx0, ry0, rx1, ry1):
        """Search for colorbar in a region using gradient analysis."""
        region = self.bgr[ry0:ry1, rx0:rx1]
        rh, rw = region.shape[:2]
        if rh < 5 or rw < 5:
            return None

        gray_region = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

        if side in ('right', 'left'):
            # Vertical colorbar: gradient along y-axis, uniform along x-axis
            grad_y = cv2.Sobel(gray_region, cv2.CV_64F, 0, 1, ksize=3)
            grad_mag = np.abs(grad_y)

            # Per-column mean gradient
            col_grad = np.mean(grad_mag, axis=0)
            if col_grad.max() > 0:
                col_grad = col_grad / col_grad.max()

            # Colorbar columns: moderate gradient (not uniform, not noise)
            mask = (col_grad > 0.03) & (col_grad < 0.85)
            best_start, best_len = self._longest_run(mask)

            if best_len < 4:
                return None

            cb_x0, cb_x1 = rx0 + best_start, rx0 + best_start + best_len

            # Vertical extent: rows where gradient is present in the bar
            bar_cols = grad_mag[:, best_start:best_start + best_len]
            row_grad = np.mean(bar_cols, axis=1)
            thresh = np.mean(row_grad) * 0.3 if np.mean(row_grad) > 0 else 0
            active = np.where(row_grad > thresh)[0]
            cb_y0 = ry0 + (active[0] if len(active) > 0 else 0)
            cb_y1 = ry0 + (active[-1] + 1 if len(active) > 0 else rh)

        else:
            # Horizontal colorbar
            grad_x = cv2.Sobel(gray_region, cv2.CV_64F, 1, 0, ksize=3)
            grad_mag = np.abs(grad_x)

            row_grad = np.mean(grad_mag, axis=1)
            if row_grad.max() > 0:
                row_grad = row_grad / row_grad.max()

            mask = (row_grad > 0.03) & (row_grad < 0.85)
            best_start, best_len = self._longest_run(mask)

            if best_len < 4:
                return None

            cb_y0, cb_y1 = ry0 + best_start, ry0 + best_start + best_len
            bar_rows = grad_mag[best_start:best_start + best_len, :]
            col_grad = np.mean(bar_rows, axis=0)
            thresh = np.mean(col_grad) * 0.3 if np.mean(col_grad) > 0 else 0
            active = np.where(col_grad > thresh)[0]
            cb_x0 = rx0 + (active[0] if len(active) > 0 else 0)
            cb_x1 = rx0 + (active[-1] + 1 if len(active) > 0 else rw)

        cb_w, cb_h = cb_x1 - cb_x0, cb_y1 - cb_y0
        if cb_w < 3 or cb_h < 10:
            return None
        if side in ('right', 'left') and cb_w > self.width * 0.15:
            return None
        if side in ('bottom', 'top') and cb_h > self.height * 0.15:
            return None

        # Confidence score
        # For a valid colorbar, the long axis should roughly match the frame dimension
        if side in ('right', 'left'):
            bar_long = cb_h
            frame_dim = self.frame_bounds[3] - self.frame_bounds[1]
        else:
            bar_long = cb_w
            frame_dim = self.frame_bounds[2] - self.frame_bounds[0]

        # Aspect score: how well does colorbar length match frame dimension?
        # A good colorbar is ~40-105% of the frame length (relaxed from 60%)
        length_ratio = bar_long / max(frame_dim, 1)
        if 0.4 <= length_ratio <= 1.05:
            aspect_score = 1.0
        elif length_ratio < 0.4:
            aspect_score = length_ratio / 0.4
        else:
            aspect_score = max(0, 1.0 - (length_ratio - 1.05) * 2)

        bar_slice = self.bgr[cb_y0:cb_y1, cb_x0:cb_x1]
        bar_gray = cv2.cvtColor(bar_slice, cv2.COLOR_BGR2GRAY)
        std_across = np.mean(np.std(bar_gray.astype(np.float64), axis=0 if side in ('right', 'left') else 1))
        grad_consistency = 1.0 - min(std_across / 128.0, 1.0)

        confidence = 0.5 * aspect_score + 0.5 * grad_consistency

        # Store length ratio and aspect for later checks
        self.colorbar_length_ratio = length_ratio
        if side in ('right', 'left'):
            self.colorbar_aspect = cb_w / max(cb_h, 1)
        else:
            self.colorbar_aspect = cb_h / max(cb_w, 1)

        return {'bounds': (cb_x0, cb_y0, cb_x1, cb_y1), 'side': side, 'confidence': confidence}

    @staticmethod
    def _longest_run(mask):
        """Find the longest consecutive True run in a boolean array."""
        best_start, best_len, cur_start, cur_len = 0, 0, 0, 0
        for i, v in enumerate(mask):
            if v:
                if cur_len == 0:
                    cur_start = i
                cur_len += 1
            else:
                if cur_len > best_len:
                    best_start, best_len = cur_start, cur_len
                cur_len = 0
        if cur_len > best_len:
            best_start, best_len = cur_start, cur_len
        return best_start, best_len

    # -----------------------------------------------------------------------
    # Step 3: Legend detection (OpenCV contour-based)
    # -----------------------------------------------------------------------

    def detect_legend(self):
        """
        Detect legend box using OpenCV contour analysis.

        Searches both inside the main frame AND in a margin band around it
        (legends are sometimes placed on or just outside the frame border).

        Plan-guided: if the plan does not mention a legend, detection is
        skipped entirely to avoid false positives from map features.

        Strategy:
        1. Search region: frame interior + 15% margin on each side
        2. cv2.findContours to extract contours
        3. cv2.approxPolyDP to fit polygons
        4. Score by: border presence, light interior, internal structure
        5. Post-check: if legend crosses frame border, flag as overlap
        """
        # Skip legend detection if plan says no legend is expected
        if self.plan_info and not self.plan_info.get('expects_legend'):
            print("\n[3/6] Detecting legend ...")
            print("  Skipped: plan does not mention a legend")
            self.legend_bounds = None
            return

        print("\n[3/6] Detecting legend ...")
        fx0, fy0, fx1, fy1 = self.frame_bounds
        fw, fh = fx1 - fx0, fy1 - fy0

        # Expand search region: add 15% margin outside frame on each side
        margin = int(min(fw, fh) * 0.12)
        sx0 = max(0, fx0 - margin)
        sy0 = max(0, fy0 - margin)
        sx1 = min(self.width, fx1 + margin)
        sy1 = min(self.height, fy1 + margin)

        search_region = self.bgr[sy0:sy1, sx0:sx1]
        search_gray = cv2.cvtColor(search_region, cv2.COLOR_BGR2GRAY)
        sh, sw = search_gray.shape

        edges = cv2.Canny(search_gray, 40, 120)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges_closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=1)

        contours, _ = cv2.findContours(
            edges_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        frame_area = fw * fh
        candidates = []

        for cnt in contours:
            x_raw, y_raw, w_raw, h_raw = cv2.boundingRect(cnt)
            area = w_raw * h_raw
            if area < 0.003 * frame_area or area > 0.35 * frame_area:
                continue

            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            if len(approx) < 4 or len(approx) > 12:
                continue

            x, y, w_rect, h_rect = cv2.boundingRect(cnt)
            aspect = h_rect / max(w_rect, 1)
            if aspect > 8 or aspect < 0.25:
                continue

            # Light interior check
            roi = search_gray[y:y + h_rect, x:x + w_rect]
            mean_brightness = np.mean(roi)
            if mean_brightness < 140:
                continue

            # Border score (relative to search region edges)
            border_score = self._border_score(edges, x, y, w_rect, h_rect)

            # Stronger border requirement for large candidates
            min_border = 0.25 if area < 0.10 * frame_area else 0.40
            if border_score < min_border:
                continue

            internal_score = self._internal_score(
                search_region[y:y + h_rect, x:x + w_rect], roi)

            rect_area = w_rect * h_rect
            cnt_area = cv2.contourArea(cnt)
            rectangularity = cnt_area / rect_area if rect_area > 0 else 0

            score = (0.25 * border_score + 0.20 * (mean_brightness / 255.0) +
                     0.30 * internal_score + 0.25 * rectangularity)

            if score > 0.35:
                # Convert to absolute coordinates
                abs_bounds = (sx0 + x, sy0 + y, sx0 + x + w_rect, sy0 + y + h_rect)
                candidates.append({
                    'bounds': abs_bounds,
                    'score': score,
                })

        if candidates:
            best = max(candidates, key=lambda c: c['score'])
            self.legend_bounds = best['bounds']
            lb = self.legend_bounds
            print(f"  Legend (bordered): ({lb[0]},{lb[1]})-({lb[2]},{lb[3]}), score={best['score']:.2f}")
            self._analyze_legend_internals()
            self._check_legend_frame_overlap()
        else:
            # Try borderless legend detection (text + marker clusters)
            self._detect_borderless_legend(search_gray, sx0, sy0, frame_area)
            if self.legend_bounds:
                self._check_legend_frame_overlap()
            else:
                print("  No legend detected")
                self.legend_bounds = None

    def _check_legend_frame_overlap(self):
        """
        Check if the legend overlaps with the main frame border.
        The legend should not touch or cross the frame border.
        """
        fx0, fy0, fx1, fy1 = self.frame_bounds
        lx0, ly0, lx1, ly1 = self.legend_bounds

        frame_margin = 3  # GMT frame line + tick marks zone

        issues = []

        # Bottom edge
        if ly1 >= fy1 - frame_margin and ly0 < fy1:
            # Legend overlaps bottom frame zone
            overlap = ly1 - (fy1 - frame_margin)
            if overlap > 0:
                issues.append(('bottom', int(overlap)))

        # Top edge
        if ly0 <= fy0 + frame_margin and ly1 > fy0:
            overlap = (fy0 + frame_margin) - ly0
            if overlap > 0:
                issues.append(('top', int(overlap)))

        # Right edge
        if lx1 >= fx1 - frame_margin and lx0 < fx1:
            overlap = lx1 - (fx1 - frame_margin)
            if overlap > 0:
                issues.append(('right', int(overlap)))

        # Left edge
        if lx0 <= fx0 + frame_margin and lx1 > fx0:
            overlap = (fx0 + frame_margin) - lx0
            if overlap > 0:
                issues.append(('left', int(overlap)))

        for edge, px in issues:
            self.failures.append({
                'item': f'图例覆盖主图框{edge}边框',
                'current': f'图例与{edge}边框重叠约 {px} px',
                'expected': '图例与图框边框之间应留有间距',
                'suggestion': (f'图例与主图框的{edge}边框重叠。'
                               '在 GMT 中调整图例位置偏移 '
                               '(gmt legend -D 参数)，'
                               '使图例完全在边框内侧或外侧。'),
                'priority': 'high',
            })

        if issues:
            print(f"  ⚠️ Legend overlaps frame border: {[(e, f'{p}px') for e, p in issues]}")

    def _detect_borderless_legend(self, search_gray, sx0, sy0, frame_area):
        """
        Detect borderless legends near frame edges.

        Strategy: scan bands along frame borders looking for organized
        clusters of colored marker patches. Legend markers are uniformly
        sized and regularly arranged in rows — very different from
        scattered map annotations.
        """
        fx0, fy0, fx1, fy1 = self.frame_bounds
        fw, fh = fx1 - fx0, fy1 - fy0
        band_width = int(min(fw, fh) * 0.15)

        best_legend = None
        best_score = 0

        # Check bottom and top bands
        for edge, frame_y, search_dir in [('bottom', fy1, 1), ('top', fy0, -1)]:
            by0 = max(0, (frame_y if search_dir < 0 else frame_y - band_width) - sy0)
            by1 = min(search_gray.shape[0],
                      (frame_y + band_width if search_dir > 0 else frame_y) - sy0)
            if by1 - by0 < 20:
                continue

            band = search_gray[by0:by1, :]
            y_offset = sy0 + by0

            # Try Otsu first (works well for clean plots), fall back to adaptive
            _, binary = cv2.threshold(band, 0, 255,
                                      cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            # If Otsu produces too few components, try adaptive
            n_test, _, _, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
            if n_test < 8:
                binary = cv2.adaptiveThreshold(
                    band, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV, 31, 5)

            n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
                binary, connectivity=8)

            elements = []
            for i in range(1, n_labels):
                cx, cy, cw, ch, area = stats[i]
                if area < 12 or area > 3000:
                    continue
                aspect = ch / max(cw, 1)
                # Markers: small, near-square patches
                is_marker = (0.2 < aspect < 4.0)
                # Text: wider components
                is_text = (cw > ch * 1.0)
                if is_marker or is_text:
                    elements.append({
                        'x': cx, 'y': cy, 'w': cw, 'h': ch,
                        'area': area, 'cy': cy + ch / 2,
                        'type': 'marker' if is_marker else 'text',
                    })

            if len(elements) < 4:
                continue

            # Must have at least some markers
            markers = [e for e in elements if e['type'] == 'marker']
            if len(markers) < 3:
                continue

            # Cluster by y-center with tight tolerance (same row)
            elems = sorted(elements, key=lambda e: e['cy'])
            row_groups = []
            used = set()
            for e in elems:
                if id(e) in used:
                    continue
                # Find all elements at this y level (within 10px)
                same_row = [o for o in elems
                           if abs(o['cy'] - e['cy']) <= 10 and id(o) not in used]
                for o in same_row:
                    used.add(id(o))
                row_groups.append(same_row)

            # Merge nearby row_groups (within 18px center-to-center)
            merged_rows = []
            for rg in sorted(row_groups, key=lambda g: np.mean([e['cy'] for e in g])):
                cy_center = np.mean([e['cy'] for e in rg])
                if merged_rows and abs(cy_center - np.mean([e['cy'] for e in merged_rows[-1]])) < 18:
                    merged_rows[-1].extend(rg)
                else:
                    merged_rows.append(rg)

            # Filter: each row must have >= 2 markers
            row_clusters = [r for r in merged_rows
                          if sum(1 for e in r if e['type'] == 'marker') >= 2]

            if len(row_clusters) < 2:
                continue

            # Filter: keep only marker-dense row clusters
            # (each row should have at least 2 markers)
            legend_rows = [r for r in row_clusters
                          if sum(1 for e in r if e['type'] == 'marker') >= 2]
            if len(legend_rows) < 2:
                continue

            # Compute bounding box from legend rows only
            all_e = [e for r in legend_rows for e in r]
            min_x = min(e['x'] for e in all_e)
            min_y = min(e['y'] for e in all_e)
            max_x = max(e['x'] + e['w'] for e in all_e)
            max_y = max(e['y'] + e['h'] for e in all_e)

            lw, lh = max_x - min_x, max_y - min_y
            l_area = lw * lh
            if l_area < 0.001 * frame_area or l_area > 0.35 * frame_area:
                continue
            if lh / max(lw, 1) > 5 or lw / max(lh, 1) > 15:
                continue

            # Score: uniformity of marker sizes + number of rows
            marker_areas = [e['area'] for e in all_e if e['type'] == 'marker']
            if marker_areas:
                cv_marker = np.std(marker_areas) / max(np.mean(marker_areas), 1)
                uniformity = 1.0 / (1.0 + cv_marker)
            else:
                uniformity = 0.5

            n_markers = len(marker_areas)
            n_texts = sum(1 for e in all_e if e['type'] == 'text')
            # A valid legend must have text labels alongside markers.
            # Clusters of markers without text are likely map features,
            # not legend items (e.g., contour labels, terrain artifacts).
            if n_texts < 2:
                continue
            score = len(legend_rows) * uniformity * (1.0 + 0.3 * n_texts)

            if score > best_score:
                best_score = score
                best_legend = {
                    'bounds': (sx0 + min_x, y_offset + min_y,
                               sx0 + max_x, y_offset + max_y),
                    'elements': all_e,
                }

        if best_legend:
            lb = best_legend['bounds']
            self.legend_bounds = lb
            print(f"  Legend (borderless): ({lb[0]},{lb[1]})-({lb[2]},{lb[3]}), "
                  f"score={best_score:.1f}")

            self.legend_markers = []
            self.legend_text_regions = []
            lx0, ly0 = lb[0], lb[1]
            for e in best_legend['elements']:
                abs_b = (lx0 + e['x'] - (lx0 - sx0), ly0 + e['y'],
                         lx0 + e['x'] - (lx0 - sx0) + e['w'], ly0 + e['y'] + e['h'])
                if e['type'] == 'marker':
                    self.legend_markers.append(abs_b)
                else:
                    self.legend_text_regions.append(abs_b)

            print(f"  Legend internals: {len(self.legend_markers)} markers, "
                  f"{len(self.legend_text_regions)} text regions")

    def _border_score(self, edges, x, y, w, h_rect):
        """Fraction of rectangle perimeter that aligns with edge pixels."""
        eh, ew = edges.shape
        y2, x2 = min(y + h_rect - 1, eh - 1), min(x + w - 1, ew - 1)
        top = edges[y, x:min(x + w, ew)]
        bot = edges[y2, x:min(x + w, ew)]
        left = edges[y:min(y + h_rect, eh), x]
        right = edges[y:min(y + h_rect, eh), x2]
        total = 2 * (w + h_rect)
        if total == 0:
            return 0
        hits = (np.sum(top > 0) + np.sum(bot > 0) +
                np.sum(left > 0) + np.sum(right > 0))
        return min(hits / (total * 0.4), 1.0)

    def _internal_score(self, bgr_patch, gray_patch):
        """Score internal structure: color patches + text produce structured variance."""
        ph, pw = gray_patch.shape
        if ph < 8 or pw < 8:
            return 0.1

        # Cell-based variance analysis
        ch, cw = max(ph // 4, 2), max(pw // 4, 2)
        cell_vars = []
        for cy in range(0, ph, ch):
            for cx in range(0, pw, cw):
                cell = gray_patch[cy:min(cy + ch, ph), cx:min(cx + cw, pw)]
                if cell.size > 0:
                    cell_vars.append(np.var(cell.astype(np.float64)))

        if not cell_vars:
            return 0
        mean_var = np.mean(cell_vars)
        var_of_vars = np.var(cell_vars)
        return min(mean_var / 600.0, 1.0) * 0.5 + min(var_of_vars / 1200.0, 1.0) * 0.5

    def _analyze_legend_internals(self):
        """Use OpenCV connectedComponentsWithStats to separate markers and text."""
        if not self.legend_bounds:
            return
        lx0, ly0, lx1, ly1 = self.legend_bounds
        roi = self.gray[ly0:ly1, lx0:lx1]
        lh, lw = roi.shape
        if lh < 5 or lw < 5:
            return

        # Otsu threshold to separate dark foreground (text + markers) from light bg
        _, binary = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Connected components with stats
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            binary, connectivity=8)

        for i in range(1, num_labels):
            cx, cy, cw, ch, area = stats[i]
            if area < 10:
                continue

            abs_x0 = lx0 + cx
            abs_y0 = ly0 + cy
            abs_x1 = lx0 + cx + cw
            abs_y1 = ly0 + cy + ch
            aspect = ch / max(cw, 1)

            # Classify: markers (small, square-ish) vs text (wider)
            if area < 800 and 0.2 < aspect < 3.0:
                self.legend_markers.append((abs_x0, abs_y0, abs_x1, abs_y1))
            elif area >= 10:
                self.legend_text_regions.append((abs_x0, abs_y0, abs_x1, abs_y1))

        print(f"  Legend internals: {len(self.legend_markers)} markers, "
              f"{len(self.legend_text_regions)} text regions")

    # -----------------------------------------------------------------------
    # Step 4: Information density analysis
    # -----------------------------------------------------------------------

    def analyze_info_density(self):
        """Analyze data density inside main frame using variance + gradient."""
        print("\n[4/6] Analyzing information density ...")
        fx0, fy0, fx1, fy1 = self.frame_bounds
        interior = self.bgr[fy0:fy1, fx0:fx1]
        interior_gray = cv2.cvtColor(interior, cv2.COLOR_BGR2GRAY)
        fh, fw = interior_gray.shape

        grid_size = 8
        h_step = max(fh // grid_size, 1)
        w_step = max(fw // grid_size, 1)
        gh, gw = fh // h_step, fw // w_step

        density = np.zeros((gh, gw), dtype=np.float32)
        for gy in range(gh):
            for gx in range(gw):
                y0, y1 = gy * h_step, min((gy + 1) * h_step, fh)
                x0, x1 = gx * w_step, min((gx + 1) * w_step, fw)
                cell = interior_gray[y0:y1, x0:x1]
                if cell.size > 0:
                    color_var = np.var(cell.astype(np.float64))
                    gy_cv, gx_cv = cv2.Sobel(cell, cv2.CV_64F, 0, 1, ksize=3), \
                                   cv2.Sobel(cell, cv2.CV_64F, 1, 0, ksize=3)
                    edge_mag = np.sqrt(gy_cv ** 2 + gx_cv ** 2)
                    edge_density = np.mean(edge_mag)
                    density[gy, gx] = color_var * 0.6 + edge_density * 0.4

        self.info_density_map = density
        v_min, v_max = density.min(), density.max()
        self.info_density_map_norm = ((density - v_min) / (v_max - v_min)
                                      if v_max > v_min else np.zeros_like(density))

        if self.legend_bounds:
            self._evaluate_legend_placement()
        else:
            print("  No legend to evaluate")

    def _evaluate_legend_placement(self):
        """Evaluate legend placement relative to information density."""
        fx0, fy0, _, _ = self.frame_bounds
        lx0, ly0, lx1, ly1 = self.legend_bounds
        h_step = (self.frame_bounds[3] - self.frame_bounds[1]) / self.info_density_map.shape[0]
        w_step = (self.frame_bounds[2] - self.frame_bounds[0]) / self.info_density_map.shape[1]

        cx = int(np.clip(((lx0 + lx1) / 2 - fx0) / w_step, 0, self.info_density_map.shape[1] - 1))
        cy = int(np.clip(((ly0 + ly1) / 2 - fy0) / h_step, 0, self.info_density_map.shape[0] - 1))

        self._legend_density = float(self.info_density_map_norm[cy, cx])
        all_d = self.info_density_map_norm.flatten()
        self._legend_percentile = float(np.sum(all_d <= self._legend_density) / len(all_d) * 100)

        corners = {
            'top-left':     self.info_density_map_norm[0, 0],
            'top-right':    self.info_density_map_norm[0, -1],
            'bottom-left':  self.info_density_map_norm[-1, 0],
            'bottom-right': self.info_density_map_norm[-1, -1],
        }
        self._best_corner = min(corners, key=corners.get)
        self._corners = corners
        print(f"  Legend density: {self._legend_density:.3f} "
              f"(percentile: {self._legend_percentile:.0f}%)")
        print(f"  Best corner: {self._best_corner}")

    # -----------------------------------------------------------------------
    # Step 5: Gap measurements
    # -----------------------------------------------------------------------

    def measure_gaps(self):
        """Measure distances between detected elements."""
        print("\n[5/6] Measuring gaps ...")
        fx0, fy0, fx1, fy1 = self.frame_bounds

        # Colorbar gap
        if self.colorbar_bounds:
            cb = self.colorbar_bounds
            gap_map = {
                'right':  cb[0] - fx1,
                'left':   fx0 - cb[2],
                'bottom': cb[1] - fy1,
                'top':    fy0 - cb[3],
            }
            self._colorbar_gap = max(0, gap_map.get(self.colorbar_side, 0))
            print(f"  Colorbar gap: {self._colorbar_gap:.0f} px (threshold: {self.min_gap} px)")

            if self._colorbar_gap < self.min_gap:
                self.failures.append({
                    'item': '色标与主图框间距',
                    'current': f'{self._colorbar_gap:.0f} px',
                    'expected': f'>={self.min_gap} px',
                    'suggestion': ('增加色标与主图框之间的距离。'
                                   '在 GMT 中使用 colorbar 的 offset 参数 '
                                   '(如 gmt colorbar -Dx+o<offset>)，'
                                   '或调整 -X/-Y 偏移量。'),
                    'priority': 'high',
                })
            elif self._colorbar_gap > self.short_side * 0.08:
                self.warnings.append({
                    'item': '色标与主图框间距过大',
                    'current': f'{self._colorbar_gap:.0f} px (图件短边的 {self._colorbar_gap/self.short_side:.1%})',
                    'suggested': f'<= {self.short_side * 0.08:.0f} px',
                    'suggestion': ('色标与主图框之间距离过大，视觉上不够紧凑。'
                                   '在 GMT 中减小 colorbar 的 offset 参数 '
                                   '(如 gmt colorbar -Dx+o<offset>)，'
                                   '使色标更靠近主图框。'),
                    'priority': 'medium',
                })
            else:
                self.passes.append(f'色标与主图框间距: {self._colorbar_gap:.0f} px (阈值: {self.min_gap} px)')
        else:
            self._colorbar_gap = None

        # Legend distances
        if self.legend_bounds:
            lx0, ly0, lx1, ly1 = self.legend_bounds
            dists = {
                'left': lx0 - fx0, 'right': fx1 - lx1,
                'top': ly0 - fy0, 'bottom': fy1 - ly1,
            }
            self._legend_distances = {k: max(0, v) for k, v in dists.items()}
            print(f"  Legend distances: { {k: f'{v:.0f}' for k, v in dists.items()} }")
            min_d = min(dists.values())
            if min_d < 5:
                self.warnings.append({
                    'item': '图例与主图边界距离',
                    'current': f'{min_d:.0f} px',
                    'suggested': '>=5 px',
                    'suggestion': '图例距离主图边界过近，建议留出更多边距。',
                    'priority': 'medium',
                })
            else:
                self.passes.append(f'图例与主图边界距离充足 (最小 {min_d:.0f} px)')
        else:
            self._legend_distances = None

    # -----------------------------------------------------------------------
    # Step 6: Overlap detection
    # -----------------------------------------------------------------------

    def detect_overlaps(self):
        """Detect overlapping elements and spacing issues."""
        print("\n[6/6] Detecting element overlaps and spacing ...")
        if self.legend_markers:
            if self.legend_text_regions:
                self._check_legend_overlaps()
            self._check_legend_spacing()
        self._check_boundary_overflow()
        if self.colorbar_bounds:
            self._check_colorbar_frame_overlap()

    def _check_legend_overlaps(self):
        """
        Check legend internal overlaps.

        In GMT legends, markers sit to the LEFT of text on the same row —
        this is normal. We only flag:
          - Cross-row overlaps (different rows occupying same space)
          - Excessive same-row horizontal overlap
          - Row vertical spacing < 2px
        """
        SAME_ROW_IOU = 0.5
        matched_pairs = []
        cross_row, same_row_overlap = [], []

        for i, (mx0, my0, mx1, my1) in enumerate(self.legend_markers):
            for j, (tx0, ty0, tx1, ty1) in enumerate(self.legend_text_regions):
                vy0, vy1 = max(my0, ty0), min(my1, ty1)
                v_overlap = max(0, vy1 - vy0)
                mh, th = my1 - my0, ty1 - ty0
                min_h = min(mh, th)

                if min_h > 0 and v_overlap / min_h > SAME_ROW_IOU:
                    matched_pairs.append((i, j))
                    h_overlap = max(0, min(mx1, tx1) - max(mx0, tx0))
                    mw = mx1 - mx0
                    tw = tx1 - tx0
                    if h_overlap / max(min(mw, tw), 1) > 0.2:
                        same_row_overlap.append({'i': i, 'j': j, 'ratio': h_overlap / max(min(mw, tw), 1)})
                else:
                    h_overlap = max(0, min(mx1, tx1) - max(mx0, tx0))
                    if h_overlap > 0 and v_overlap > 0:
                        ma = mw = mx1 - mx0
                        ta = tw = tx1 - tx0
                        cross_row.append({'i': i, 'j': j,
                                          'ratio': h_overlap * v_overlap / max(min(ma, ta), 1)})

        # Row spacing check
        all_centers = ([(('m', i), (self.legend_markers[i][1] + self.legend_markers[i][3]) / 2)
                         for i in range(len(self.legend_markers))] +
                       [(('t', j), (self.legend_text_regions[j][1] + self.legend_text_regions[j][3]) / 2)
                         for j in range(len(self.legend_text_regions))])
        all_centers.sort(key=lambda x: x[1])
        rows, cur = [], [all_centers[0]] if all_centers else []
        for item in all_centers[1:]:
            if abs(item[1] - cur[-1][1]) < 8:
                cur.append(item)
            else:
                rows.append(cur)
                cur = [item]
        if cur:
            rows.append(cur)

        row_issue = False
        for r in range(1, len(rows)):
            if (min(item[1] for item in rows[r]) -
                max(item[1] for item in rows[r - 1])) < 2:
                row_issue = True
                break

        # Report
        if cross_row:
            for ov in cross_row[:3]:  # max 3
                self.failures.append({
                    'item': '图例跨行文字标识重叠',
                    'current': f"重叠率 {ov['ratio']:.1%}",
                    'expected': '无跨行重叠',
                    'suggestion': ('图例内不同行的元素重叠。增大 GMT legend 行间距，'
                                   '或调整字体大小 (--FONT_ANNOT_PRIMARY)。'),
                    'priority': 'high',
                })
        if row_issue:
            self.failures.append({
                'item': '图例行间距过小',
                'current': '行间距 < 2 px',
                'expected': '>=2 px',
                'suggestion': '增加 GMT legend 中行与行之间的间距。',
                'priority': 'high',
            })
        if same_row_overlap:
            for ov in same_row_overlap[:3]:
                self.warnings.append({
                    'item': '图例同行文字标识水平重叠',
                    'current': f"重叠率 {ov['ratio']:.1%}",
                    'suggested': '< 20%',
                    'suggestion': '增加 legend 中标识与文字之间的水平间距。',
                    'priority': 'medium',
                })
        if not cross_row and not row_issue and not same_row_overlap:
            if self.legend_markers and self.legend_text_regions:
                self.passes.append(
                    f'图例内部无异常重叠 '
                    f'({len(self.legend_markers)} 标识, {len(self.legend_text_regions)} 文字, '
                    f'{len(matched_pairs)} 同行匹配)')

    def _check_legend_spacing(self):
        """
        Check spacing between legend markers.

        Detects:
        - Excessive horizontal gaps between columns of markers
        - Inconsistent column spacing (some gaps much wider than others)
        - Excessive vertical gaps between rows
        - Marker-to-gap ratio imbalance (markers tiny, gaps huge)
        """
        markers = self.legend_markers
        if len(markers) < 4:
            return

        # Step 1: Group markers by row (y-center proximity)
        marker_centers = [(i, (m[0] + m[2]) / 2, (m[1] + m[3]) / 2,
                           m[2] - m[0], m[3] - m[1])
                          for i, m in enumerate(markers)]
        # Sort by y-center
        sorted_by_y = sorted(marker_centers, key=lambda m: m[2])

        rows = []
        cur_row = [sorted_by_y[0]]
        for m in sorted_by_y[1:]:
            cur_y_avg = np.mean([x[2] for x in cur_row])
            if abs(m[2] - cur_y_avg) <= 12:  # same row if y-center within 12px
                cur_row.append(m)
            else:
                if len(cur_row) >= 2:
                    rows.append(sorted(cur_row, key=lambda x: x[1]))  # sort by x
                cur_row = [m]
        if len(cur_row) >= 2:
            rows.append(sorted(cur_row, key=lambda x: x[1]))

        if len(rows) < 2:
            return

        # Step 2: Compute horizontal gaps within each row
        # marker tuple: (index, cx, cy, width, height)
        # right edge = cx + width/2, left edge = cx - width/2
        all_h_gaps = []
        row_h_gaps = []
        for row in rows:
            gaps = []
            for k in range(len(row) - 1):
                right_edge = row[k][1] + row[k][3] / 2    # cx + w/2
                next_left  = row[k + 1][1] - row[k + 1][3] / 2  # cx - w/2
                gap = next_left - right_edge
                if gap >= 0:
                    gaps.append(gap)
            if gaps:
                row_h_gaps.append(gaps)
                all_h_gaps.extend(gaps)

        if not all_h_gaps:
            return

        # Step 3: Compute vertical gaps between rows
        row_y_centers = [np.mean([m[2] for m in row]) for row in rows]
        row_y_centers.sort()
        v_gaps = [row_y_centers[i + 1] - row_y_centers[i]
                  for i in range(len(row_y_centers) - 1)]

        # Step 4: Compute marker sizes
        marker_widths = [m[3] for m in marker_centers]
        marker_heights = [m[4] for m in marker_centers]
        avg_marker_w = np.mean(marker_widths) if marker_widths else 1
        avg_marker_h = np.mean(marker_heights) if marker_heights else 1

        # Step 5: Evaluate spacing issues
        issues = []

        # 5a: Excessive horizontal gaps (gap > 4x average marker width)
        large_gaps = [g for g in all_h_gaps if g > 4.0 * avg_marker_w]
        if len(large_gaps) > 0:
            max_gap = max(large_gaps)
            ratio = max_gap / avg_marker_w if avg_marker_w > 0 else 0
            issues.append({
                'item': '图例列间距过大',
                'type': 'horizontal',
                'detail': (f'最大列间距 {max_gap:.0f} px，为标识宽度 '
                          f'({avg_marker_w:.0f} px) 的 {ratio:.1f} 倍'),
                'severity': 'failure' if ratio > 6 else 'warning',
            })

        # 5b: Inconsistent horizontal spacing within a row
        for i, gaps in enumerate(row_h_gaps):
            if len(gaps) >= 2:
                gap_std = np.std(gaps)
                gap_mean = np.mean(gaps)
                if gap_mean > 0 and gap_std / gap_mean > 0.6:
                    issues.append({
                        'item': f'图例第{i+1}行列间距不均匀',
                        'type': 'horizontal',
                        'detail': (f'列间距范围 {min(gaps):.0f}-{max(gaps):.0f} px，'
                                  f'差异 {gap_std/gap_mean:.1%}'),
                        'severity': 'warning',
                    })
                    break  # one row is enough to flag

        # 5c: Excessive vertical gaps between rows (> 3x marker height)
        large_v_gaps = [g for g in v_gaps if g > 3.0 * avg_marker_h]
        if len(large_v_gaps) > 0:
            max_v_gap = max(large_v_gaps)
            v_ratio = max_v_gap / avg_marker_h if avg_marker_h > 0 else 0
            issues.append({
                'item': '图例行间距过大',
                'type': 'vertical',
                'detail': (f'最大行间距 {max_v_gap:.0f} px，为标识高度 '
                          f'({avg_marker_h:.0f} px) 的 {v_ratio:.1f} 倍'),
                'severity': 'failure' if v_ratio > 5 else 'warning',
            })

        # 5d: Marker-to-gap ratio — markers are tiny compared to gaps
        # Compute total width of a "unit" (marker + gap to next)
        if avg_marker_w > 0:
            total_gap_sum = sum(all_h_gaps)
            total_marker_sum = sum(marker_widths)
            if total_marker_sum > 0 and total_gap_sum > total_marker_sum * 2:
                issues.append({
                    'item': '图例标识占比过小',
                    'type': 'proportion',
                    'detail': (f'标识总宽度 {total_marker_sum:.0f} px，间隙总宽度 '
                              f'{total_gap_sum:.0f} px，标识仅占 '
                              f'{total_marker_sum/(total_marker_sum+total_gap_sum):.1%}'),
                    'severity': 'warning',
                })

        # Report issues
        for issue in issues:
            entry = {
                'item': issue['item'],
                'current': issue['detail'],
                'expected': '间距与标识尺寸比例协调',
                'suggested': (f'水平间距 < {4.0 * avg_marker_w:.0f} px (4x标识宽)，'
                             f'垂直间距 < {3.0 * avg_marker_h:.0f} px (3x标识高)，'
                             '各列间距均匀'),
                'suggestion': ('在 GMT legend 文件中调整标识之间的间距。'
                               '可通过修改 legend 文件中每行的列宽参数，'
                               '或减少 N (列数) 来缩小间距。'),
                'priority': 'high' if issue['severity'] == 'failure' else 'medium',
            }
            if issue['severity'] == 'failure':
                self.failures.append(entry)
            else:
                self.warnings.append(entry)

        if not issues:
            avg_h_gap = np.mean(all_h_gaps) if all_h_gaps else 0
            avg_v_gap = np.mean(v_gaps) if v_gaps else 0
            self.passes.append(
                f'图例间距合理 (水平均距 {avg_h_gap:.0f} px/标识宽{avg_marker_w:.0f} px, '
                f'垂直均距 {avg_v_gap:.0f} px/标识高{avg_marker_h:.0f} px)')

    def _check_boundary_overflow(self):
        """Check if detected elements extend beyond image boundaries."""
        elements = [('主图框', self.frame_bounds)]
        if self.colorbar_bounds:
            elements.append(('色标', self.colorbar_bounds))
        if self.legend_bounds:
            elements.append(('图例', self.legend_bounds))

        overflows = []
        for name, (x0, y0, x1, y1) in elements:
            issues = []
            if x0 < 0:
                issues.append(f'左边界超出 {abs(x0)} px')
            if y0 < 0:
                issues.append(f'上边界超出 {abs(y0)} px')
            if x1 >= self.width:
                issues.append(f'右边界超出 {x1 - self.width + 1} px')
            if y1 >= self.height:
                issues.append(f'下边界超出 {y1 - self.height + 1} px')
            if issues:
                overflows.append((name, issues))

        for name, issues in overflows:
            self.failures.append({
                'item': f'{name}超出图件边界',
                'current': '; '.join(issues),
                'expected': '所有元素在图件边界内',
                'suggestion': ('检查 GMT -X/-Y 偏移量、投影尺寸 -J 参数，'
                               '确保所有内容在纸张范围内。'),
                'priority': 'high',
            })
        if not overflows:
            self.passes.append('所有元素在图件边界内')

    def _check_colorbar_frame_overlap(self):
        """Check if colorbar overlaps main frame."""
        fx0, fy0, fx1, fy1 = self.frame_bounds
        cx0, cy0, cx1, cy1 = self.colorbar_bounds
        ox0, oy0 = max(fx0, cx0), max(fy0, cy0)
        ox1, oy1 = min(fx1, cx1), min(fy1, cy1)
        if ox0 < ox1 and oy0 < oy1:
            overlap = (ox1 - ox0) * (oy1 - oy0)
            cb_area = (cx1 - cx0) * (cy1 - cy0)
            if cb_area > 0 and overlap / cb_area > 0.05:
                self.failures.append({
                    'item': '色标与主图框重叠',
                    'current': f'重叠 {overlap / cb_area:.1%}',
                    'expected': '无重叠',
                    'suggestion': ('色标与主图框重叠。增加色标偏移量 '
                                   '(gmt colorbar -Dx+o<offset>)。'),
                    'priority': 'high',
                })

    # -----------------------------------------------------------------------
    # Step 7: Colorbar detail checks
    # -----------------------------------------------------------------------

    def check_colorbar_details(self):
        """Orchestrate detailed colorbar checks."""
        print("\n[7/9] Checking colorbar details ...")
        if not self.colorbar_bounds:
            print("  No colorbar to check")
            return
        self._check_colorbar_alignment()
        self._check_colorbar_length_proportion()
        self._check_colorbar_aspect_ratio()
        self._check_colorbar_text_size()

    def _check_colorbar_alignment(self):
        """Check if colorbar edges align with main frame edges.

        For a right/left colorbar, top and bottom should align with frame top/bottom.
        For a bottom/top colorbar, left and right should align with frame left/right.
        """
        fx0, fy0, fx1, fy1 = self.frame_bounds
        cx0, cy0, cx1, cy1 = self.colorbar_bounds
        fh = fy1 - fy0
        fw = fx1 - fx0
        ALIGN_TOLERANCE = 0.04  # 4% of frame dimension

        if self.colorbar_side in ('right', 'left'):
            top_off = abs(cy0 - fy0) / max(fh, 1)
            bottom_off = abs(cy1 - fy1) / max(fh, 1)
            max_off = max(top_off, bottom_off)
            if max_off > ALIGN_TOLERANCE:
                details = []
                if top_off > ALIGN_TOLERANCE:
                    details.append(f"顶部偏差 {cy0 - fy0:+d} px ({top_off:.1%})")
                if bottom_off > ALIGN_TOLERANCE:
                    details.append(f"底部偏差 {cy1 - fy1:+d} px ({bottom_off:.1%})")
                self.failures.append({
                    'item': '色标与主图框y方向未对齐',
                    'current': '; '.join(details),
                    'expected': f'偏差 < {ALIGN_TOLERANCE:.0%} 图框高度',
                    'suggestion': ('色标条应与主图框在y方向平齐。在GMT中调整 '
                                   'colorbar 的 -D 参数偏移量，使色标上下端与主图框对齐。'
                                   '可使用 gmt colorbar -Dx+n 在指定位置绘制。'),
                    'priority': 'high',
                })
            else:
                self.passes.append(
                    f'色标与主图框y方向对齐 (顶部偏差 {top_off:.1%}, 底部偏差 {bottom_off:.1%})')
        else:
            left_off = abs(cx0 - fx0) / max(fw, 1)
            right_off = abs(cx1 - fx1) / max(fw, 1)
            max_off = max(left_off, right_off)
            if max_off > ALIGN_TOLERANCE:
                details = []
                if left_off > ALIGN_TOLERANCE:
                    details.append(f"左侧偏差 {cx0 - fx0:+d} px ({left_off:.1%})")
                if right_off > ALIGN_TOLERANCE:
                    details.append(f"右侧偏差 {cx1 - fx1:+d} px ({right_off:.1%})")
                self.failures.append({
                    'item': '色标与主图框x方向未对齐',
                    'current': '; '.join(details),
                    'expected': f'偏差 < {ALIGN_TOLERANCE:.0%} 图框宽度',
                    'suggestion': ('色标条应与主图框在x方向平齐。在GMT中调整 '
                                   'colorbar 的 -D 参数偏移量。'),
                    'priority': 'high',
                })
            else:
                self.passes.append(
                    f'色标与主图框x方向对齐 (左侧偏差 {left_off:.1%}, 右侧偏差 {right_off:.1%})')

    def _check_colorbar_length_proportion(self):
        """Check if colorbar length is sufficient relative to frame dimension.

        A good colorbar should be 60-100% of the corresponding frame dimension.
        """
        if self.colorbar_length_ratio is None:
            return

        ratio = self.colorbar_length_ratio
        if ratio < 0.5:
            self.warnings.append({
                'item': '色标相对于主图太短',
                'current': f'色标长度为主图对应维度的 {ratio:.1%}',
                'suggested': '>= 60%',
                'suggestion': ('色标长度应至少为主图对应维度的60%。'
                               '在GMT中使用 colorbar 的 +w<length>/<width> 参数增加色标长度，'
                               '或调整 -J 投影参数使色标更贴合主图尺寸。'),
                'priority': 'medium',
            })
        elif 0.5 <= ratio < 0.6:
            self.warnings.append({
                'item': '色标长度略短',
                'current': f'色标长度为主图对应维度的 {ratio:.1%}',
                'suggested': '>= 60%',
                'suggestion': ('色标长度略短于推荐值。可考虑增加色标长度使其'
                               '接近主图对应维度的60%以上。'),
                'priority': 'low',
            })
        else:
            self.passes.append(f'色标长度合适 (为主图对应维度的 {ratio:.1%})')

    def _check_colorbar_aspect_ratio(self):
        """Check colorbar width-to-length ratio.

        For a vertical colorbar, width/height should be ~0.02-0.10.
        A ratio > 0.12 suggests the colorbar is too wide, which can cause
        text labels to be squeezed or the bar to look disproportionate.
        """
        if self.colorbar_aspect is None:
            return

        aspect = self.colorbar_aspect
        if self.colorbar_side in ('right', 'left'):
            # Vertical colorbar: width / height
            if aspect > 0.12:
                self.failures.append({
                    'item': '色标宽高比例失调（色标过宽）',
                    'current': f'色标宽高比 {aspect:.2f} (宽/高)，文字可能被挤压',
                    'expected': '宽高比 <= 0.12 (色标应细长)',
                    'suggestion': ('色标宽度相对于高度过大，可能导致标签文字被挤压。'
                                   '在GMT中使用 colorbar 的 +w<length>/<width> 参数调整色标宽度，'
                                   '或将色标文字旋转方向调整为平行于色标方向。'),
                    'priority': 'high',
                })
            elif aspect > 0.10:
                self.warnings.append({
                    'item': '色标宽高比例略大',
                    'current': f'色标宽高比 {aspect:.2f} (宽/高)',
                    'suggested': '<= 0.10',
                    'suggestion': '色标略宽，建议减小宽度使色标更细长。',
                    'priority': 'medium',
                })
            else:
                self.passes.append(f'色标宽高比例合适 ({aspect:.2f})')
        else:
            # Horizontal colorbar: height / width
            if aspect > 0.12:
                self.failures.append({
                    'item': '色标高宽比例失调（色标过高）',
                    'current': f'色标高宽比 {aspect:.2f} (高/宽)',
                    'expected': '高宽比 <= 0.12',
                    'suggestion': '色标高度相对于宽度过大。调整 colorbar +w 参数。',
                    'priority': 'high',
                })
            elif aspect > 0.10:
                self.warnings.append({
                    'item': '色标高宽比例略大',
                    'current': f'色标高宽比 {aspect:.2f} (高/宽)',
                    'suggested': '<= 0.10',
                    'suggestion': '色标略高，建议减小高度。',
                    'priority': 'medium',
                })
            else:
                self.passes.append(f'色标高宽比例合适 ({aspect:.2f})')

    def _check_colorbar_text_size(self):
        """Estimate font size of colorbar label text.

        Scans the region near the colorbar for text components,
        estimates character pixel height, and flags if too small.
        """
        cx0, cy0, cx1, cy1 = self.colorbar_bounds
        MARGIN = 40  # px to search around colorbar for labels

        if self.colorbar_side == 'right':
            search_x0 = cx0
            search_x1 = min(self.width, cx1 + MARGIN)
            search_y0, search_y1 = cy0, cy1
        elif self.colorbar_side == 'left':
            search_x0 = max(0, cx0 - MARGIN)
            search_x1 = cx1
            search_y0, search_y1 = cy0, cy1
        elif self.colorbar_side == 'bottom':
            search_x0, search_x1 = cx0, cx1
            search_y0 = cy0
            search_y1 = min(self.height, cy1 + MARGIN)
        else:
            search_x0, search_x1 = cx0, cx1
            search_y0 = max(0, cy0 - MARGIN)
            search_y1 = cy1

        if search_x1 - search_x0 < 10 or search_y1 - search_y0 < 10:
            return

        roi = self.gray[search_y0:search_y1, search_x0:search_x1]
        _, binary = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        n_labels, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)

        text_heights = []
        for i in range(1, n_labels):
            _, _, cw, ch, area = stats[i]
            if area < 10:
                continue
            aspect_r = ch / max(cw, 1)
            # Text components: taller than wide or roughly square, small to medium size
            if 0.3 < aspect_r < 5.0 and area < 2000:
                text_heights.append(ch)

        if not text_heights:
            return

        median_h = np.median(text_heights)
        # For printed figures at 300 DPI, 8px ≈ 7pt (barely readable)
        MIN_HEIGHT = 10
        WARN_HEIGHT = 14

        if median_h < MIN_HEIGHT:
            self.warnings.append({
                'item': '色标标签字体过小',
                'current': f'估算字高约 {median_h:.0f} px',
                'suggested': f'>= {MIN_HEIGHT} px',
                'suggestion': ('色标标签文字过小，影响可读性。在GMT中使用 '
                               'gmt set FONT_ANNOT_PRIMARY=<size> 增大色标标注字体。'),
                'priority': 'medium',
            })
        elif median_h < WARN_HEIGHT:
            self.warnings.append({
                'item': '色标标签字体偏小',
                'current': f'估算字高约 {median_h:.0f} px',
                'suggested': f'>= {WARN_HEIGHT} px',
                'suggestion': '色标标签文字略小，建议增大字体以提高可读性。',
                'priority': 'low',
            })
        else:
            self.passes.append(f'色标标签字体大小合适 (估算字高 ~{median_h:.0f} px)')

    # -----------------------------------------------------------------------
    # Step 8: Legend detail checks
    # -----------------------------------------------------------------------

    def check_legend_details(self):
        """Orchestrate detailed legend checks."""
        print("\n[8/9] Checking legend details ...")
        if not self.legend_bounds:
            print("  No legend to check")
            return
        self._check_legend_floating()
        self._check_legend_corner_proximity()
        self._check_legend_marker_text_gap()
        self._check_legend_marker_shape()
        self._check_legend_column_spacing_close()
        self._check_legend_compactness()

    def _check_legend_floating(self):
        """Check if legend is floating far from all frame edges.

        A legend inside the frame should be near at least one edge.
        If all 4 distances to frame edges exceed thresholds, the legend
        is "floating" and should be repositioned.
        """
        fx0, fy0, fx1, fy1 = self.frame_bounds
        lx0, ly0, lx1, ly1 = self.legend_bounds

        # Distances to frame edges (negative = outside frame)
        dists = {
            'left': lx0 - fx0,
            'right': fx1 - lx1,
            'top': ly0 - fy0,
            'bottom': fy1 - ly1,
        }

        # Only check floating when legend is inside the frame
        if min(dists.values()) < 0:
            return  # Already flagged as frame overlap

        fw, fh = fx1 - fx0, fy1 - fy0
        # If the minimum distance to any edge is > 15% of frame dimension,
        # the legend is floating
        min_edge_dist = min(
            dists['left'] / max(fw, 1),
            dists['right'] / max(fw, 1),
            dists['top'] / max(fh, 1),
            dists['bottom'] / max(fh, 1),
        )

        if min_edge_dist > 0.15:
            self.failures.append({
                'item': '图例距离主图边缘太远（悬浮）',
                'current': (f'距左{dists["left"]:.0f}px 距右{dists["right"]:.0f}px '
                           f'距上{dists["top"]:.0f}px 距下{dists["bottom"]:.0f}px'),
                'expected': '至少一侧距离 < 15% 图框尺寸',
                'suggestion': ('图例悬浮在主图中央区域，应靠近某个边缘放置。'
                               '在GMT中调整 legend 的 -D 参数，将图例移动到靠近'
                               '图框边角的位置（如右下角 -DjRB 或左上角 -DjLT）。'),
                'priority': 'high',
            })
        elif min_edge_dist > 0.10:
            self.warnings.append({
                'item': '图例位置偏中央',
                'current': f'最小边缘距离为图框尺寸的 {min_edge_dist:.1%}',
                'suggested': '<= 10%',
                'suggestion': '图例建议更靠近图框边缘放置。',
                'priority': 'medium',
            })
        else:
            nearest = min(dists, key=dists.get)
            self.passes.append(f'图例靠近主图边缘 (最近边: {nearest}, {dists[nearest]:.0f}px)')

    def _check_legend_corner_proximity(self):
        """Check if legend is close to at least one corner.

        If legend center is far from all 4 corners, it may look disconnected.
        """
        lx0, ly0, lx1, ly1 = self.legend_bounds
        lcx = (lx0 + lx1) / 2
        lcy = (ly0 + ly1) / 2

        corners = {
            'top-left': (0, 0),
            'top-right': (self.width - 1, 0),
            'bottom-left': (0, self.height - 1),
            'bottom-right': (self.width - 1, self.height - 1),
        }

        diag = np.sqrt(self.width ** 2 + self.height ** 2)
        corner_dists = {}
        for name, (cx, cy) in corners.items():
            corner_dists[name] = np.sqrt((lcx - cx) ** 2 + (lcy - cy) ** 2) / diag

        min_corner = min(corner_dists, key=corner_dists.get)
        min_dist = corner_dists[min_corner]

        if min_dist > 0.35:
            self.warnings.append({
                'item': '图例远离所有角落',
                'current': f'距最近角 ({min_corner}) {min_dist:.1%} 对角线长度',
                'suggested': '<= 35% 对角线长度',
                'suggestion': ('图例距离四个角落都较远。'
                               '考虑将图例移至最近的角落附近，使其与图面布局更协调。'
                               '使用 gmt legend -D 参数指定角落位置。'),
                'priority': 'medium',
            })
        else:
            self.passes.append(f'图例靠近 {min_corner} 角落 (距离 {min_dist:.1%} 对角线)')

    def _check_legend_marker_text_gap(self):
        """Check horizontal gap between legend markers and their text.

        In a well-formatted legend, markers sit to the left of their text
        with a small gap. No gap or extremely tiny gap looks crowded.
        """
        if not self.legend_markers or not self.legend_text_regions:
            return

        MIN_GAP = 4   # px — below this is a failure
        WARN_GAP = 8  # px — below this is a warning

        too_close = []
        no_gap = []

        for i, (mx0, my0, mx1, my1) in enumerate(self.legend_markers):
            mcy = (my0 + my1) / 2
            mh = my1 - my0
            for j, (tx0, ty0, tx1, ty1) in enumerate(self.legend_text_regions):
                tcy = (ty0 + ty1) / 2
                th = ty1 - ty0
                # Check if same row: vertical overlap > 40%
                v_overlap = max(0, min(my1, ty1) - max(my0, ty0))
                min_h = min(mh, th)
                if min_h > 0 and v_overlap / min_h > 0.4:
                    # Text is to the right of marker
                    gap = tx0 - mx1
                    if gap < MIN_GAP:
                        no_gap.append({'i': i, 'j': j, 'gap': gap})
                    elif gap < WARN_GAP:
                        too_close.append({'i': i, 'j': j, 'gap': gap})

        if no_gap:
            gaps_str = ', '.join(f'{g["gap"]:.0f}px' for g in no_gap[:3])
            if len(no_gap) > 3:
                gaps_str += f' 等{len(no_gap)}处'
            self.failures.append({
                'item': '图例标注与文字间距过小（紧贴）',
                'current': f'最小间距: {gaps_str}',
                'expected': f'>={MIN_GAP} px',
                'suggestion': ('图例中色块标识和文字之间几乎无间距。'
                               '在GMT legend 文件中增加列宽参数，'
                               '或在前导字符串后添加空格来增加间距。'),
                'priority': 'high',
            })
        elif too_close:
            gaps_str = ', '.join(f'{g["gap"]:.0f}px' for g in too_close[:3])
            self.warnings.append({
                'item': '图例标注与文字间距偏小',
                'current': f'间距: {gaps_str}',
                'suggested': f'>={WARN_GAP} px',
                'suggestion': '图例标识与文字间距略小，建议增大间距。',
                'priority': 'medium',
            })
        elif self.legend_text_regions:
            self.passes.append('图例标注与文字间距合适')

    def _check_legend_marker_shape(self):
        """Check if legend markers have reasonable proportions.

        Markers should be roughly square; stretched markers look unprofessional.
        """
        if not self.legend_markers:
            return

        MAX_ASPECT = 4.0  # width/height or height/width
        bad_markers = []
        for i, (mx0, my0, mx1, my1) in enumerate(self.legend_markers):
            mw, mh = mx1 - mx0, my1 - my0
            if mw > 0 and mh > 0:
                aspect = max(mw / mh, mh / mw)
                if aspect > MAX_ASPECT:
                    direction = '过长' if mw > mh else '过高'
                    bad_markers.append({
                        'i': i, 'w': mw, 'h': mh,
                        'aspect': aspect, 'direction': direction,
                    })

        if bad_markers:
            details = []
            for bm in bad_markers[:3]:
                details.append(f'标识{bm["w"]}x{bm["h"]}px (宽高比 {bm["aspect"]:.1f}, {bm["direction"]})')
            self.failures.append({
                'item': '图例颜色标注形状过长',
                'current': '; '.join(details),
                'expected': '宽高比 <= 4.0 (接近正方形)',
                'suggestion': ('图例中的颜色标注（色块）过长或过高。'
                               '在GMT legend 文件中检查 N (列数) 和 symbol 的尺寸参数，'
                               '使用 S 符号时指定合适的尺寸使标识接近正方形。'),
                'priority': 'high',
            })
        else:
            avg_w = np.mean([m[2] - m[0] for m in self.legend_markers])
            avg_h = np.mean([m[3] - m[1] for m in self.legend_markers])
            self.passes.append(
                f'图例标识形状合理 (均宽 {avg_w:.0f}px, 均高 {avg_h:.0f}px, '
                f'宽高比 {max(avg_w/avg_h, avg_h/avg_w):.1f})')

    def _check_legend_column_spacing_close(self):
        """Check if legend columns are too close together.

        Complements the existing _check_legend_spacing (which looks for
        gaps that are too large). This checks for gaps that are too small.
        """
        markers = self.legend_markers
        if len(markers) < 3:
            return

        MIN_COL_GAP = 5  # px

        marker_centers = [(i, (m[0] + m[2]) / 2, (m[1] + m[3]) / 2,
                           m[2] - m[0], m[3] - m[1])
                         for i, m in enumerate(markers)]
        sorted_by_y = sorted(marker_centers, key=lambda m: m[2])

        rows = []
        cur_row = [sorted_by_y[0]]
        for m in sorted_by_y[1:]:
            cur_y_avg = np.mean([x[2] for x in cur_row])
            if abs(m[2] - cur_y_avg) <= 12:
                cur_row.append(m)
            else:
                if len(cur_row) >= 2:
                    rows.append(sorted(cur_row, key=lambda x: x[1]))
                cur_row = [m]
        if len(cur_row) >= 2:
            rows.append(sorted(cur_row, key=lambda x: x[1]))

        close_gaps = []
        for row_idx, row in enumerate(rows):
            for k in range(len(row) - 1):
                right_edge = row[k][1] + row[k][3] / 2
                next_left = row[k + 1][1] - row[k + 1][3] / 2
                gap = next_left - right_edge
                if 0 <= gap < MIN_COL_GAP:
                    close_gaps.append({'row': row_idx, 'gap': gap})

        if close_gaps:
            gaps_str = ', '.join(
                f'行{g["row"]+1}: {g["gap"]:.0f}px' for g in close_gaps[:3])
            if len(close_gaps) > 3:
                gaps_str += f' 等{len(close_gaps)}处'
            self.failures.append({
                'item': '图例列间距过近',
                'current': gaps_str,
                'expected': f'>={MIN_COL_GAP} px',
                'suggestion': ('图例中相邻列之间距离过近，标识挤在一起。'
                               '在GMT legend 文件中增加各列之间的间距，'
                               '或调整 N (列数) 参数。'),
                'priority': 'high',
            })

    def _check_legend_compactness(self):
        """Check legend compactness (foreground vs background ratio).

        If the legend has excessive whitespace (foreground area < 15% of
        legend area), the legend is not compact enough.
        """
        lx0, ly0, lx1, ly1 = self.legend_bounds
        l_area = (lx1 - lx0) * (ly1 - ly0)
        if l_area <= 0:
            return

        # Compute total area of markers and text
        fg_area = 0
        for mx0, my0, mx1, my1 in self.legend_markers:
            fg_area += (mx1 - mx0) * (my1 - my0)
        for tx0, ty0, tx1, ty1 in self.legend_text_regions:
            fg_area += (tx1 - tx0) * (ty1 - ty0)

        if fg_area <= 0 or l_area <= 0:
            return

        fg_ratio = fg_area / l_area

        if fg_ratio < 0.10:
            self.failures.append({
                'item': '图例背景留白过多',
                'current': f'内容仅占图例区域的 {fg_ratio:.1%}',
                'expected': '>= 15%',
                'suggestion': ('图例中空白区域过多，版面不够紧凑。'
                               '在GMT legend 文件中减少不必要的空行，'
                               '或缩小图例框的尺寸。也可调整 N (列数) 使排列更紧凑。'),
                'priority': 'high',
            })
        elif fg_ratio < 0.15:
            self.warnings.append({
                'item': '图例背景留白偏多',
                'current': f'内容占图例区域的 {fg_ratio:.1%}',
                'suggested': '>= 15%',
                'suggestion': '图例空白较多，可考虑更紧凑的排列。',
                'priority': 'medium',
            })
        else:
            self.passes.append(f'图例紧凑度合理 (内容占比 {fg_ratio:.1%})')

    # -----------------------------------------------------------------------
    # Step 9: Scale bar detection
    # -----------------------------------------------------------------------

    def detect_scale_bar(self):
        """Detect scale bar and check if it overlaps the main frame border.

        A GMT scale bar is a narrow rectangle with alternating black/white
        segments, typically located below or inside the bottom of the frame.

        Plan-guided: if the plan does not mention a scale bar, detection is
        skipped to avoid false positives.
        """
        # Skip scale bar detection if plan says no scale bar is expected
        if self.plan_info and not self.plan_info.get('expects_scale_bar'):
            print("\n[9/9] Checking scale bar ...")
            print("  Skipped: plan does not mention a scale bar")
            return

        print("\n[9/9] Checking scale bar ...")
        fx0, fy0, fx1, fy1 = self.frame_bounds
        fh = fy1 - fy0

        # Search below the main frame (common GMT scale bar position)
        search_y0 = fy1 - int(fh * 0.08)
        search_y1 = min(fy1 + int(fh * 0.25), self.height)
        search_x0 = fx0 + int((fx1 - fx0) * 0.1)
        search_x1 = fx1 - int((fx1 - fx0) * 0.1)

        if search_y1 - search_y0 < 10 or search_x1 - search_x0 < 20:
            print("  Search region too small for scale bar")
            return

        roi = self.gray[search_y0:search_y1, search_x0:search_x1]
        rh, rw = roi.shape

        # Scale bars have alternating dark/light segments along x-axis
        # Compute horizontal gradient to find alternating pattern
        if rw < 20:
            return

        grad_x = cv2.Sobel(roi, cv2.CV_64F, 1, 0, ksize=3)
        grad_mag = np.abs(grad_x)

        # Scale bar region should have high horizontal gradient
        # (alternating segments) concentrated in a narrow band
        row_grad = np.mean(grad_mag, axis=1)
        if row_grad.max() > 0:
            row_grad_norm = row_grad / row_grad.max()

        # Find rows with elevated gradient (alternating pattern)
        grad_thresh = 0.15
        active_rows = np.where(row_grad_norm > grad_thresh)[0]
        if len(active_rows) < 3:
            print("  No scale bar pattern detected")
            return

        # Find contiguous blocks of active rows
        groups = self._group_values(active_rows, gap=5)
        for g in groups:
            if len(g) < 3:
                continue
            sb_y0 = search_y0 + g[0]
            sb_y1 = search_y0 + g[-1] + 1

            # Find horizontal extent with significant alternating pattern
            col_grad = np.mean(grad_mag[g[0]:g[-1] + 1, :], axis=0)
            if col_grad.max() > 0:
                col_grad_norm = col_grad / col_grad.max()
            else:
                continue
            active_cols = np.where(col_grad_norm > grad_thresh)[0]
            if len(active_cols) < 5:
                continue
            col_groups = self._group_values(active_cols, gap=20)
            for cg in col_groups:
                if len(cg) < 5:
                    continue
                sb_x0 = search_x0 + cg[0]
                sb_x1 = search_x0 + cg[-1] + 1

                sb_w, sb_h = sb_x1 - sb_x0, sb_y1 - sb_y0
                if sb_w < 15 or sb_h < 3 or sb_h > fh * 0.1:
                    continue
                if sb_w / max(sb_h, 1) < 3:
                    continue

                # Found a scale bar candidate
                self._scale_bar_detected = True
                print(f"  Scale bar detected: ({sb_x0},{sb_y0})-({sb_x1},{sb_y1}), "
                      f"{sb_w}x{sb_h}px")

                # Check overlap with frame bottom border
                frame_bottom_zone = fy1 + 5
                if sb_y0 <= frame_bottom_zone <= sb_y1:
                    overlap = frame_bottom_zone - sb_y0
                    self.failures.append({
                        'item': '比例尺覆盖主图框边框',
                        'current': f'比例尺与图框底部重叠约 {overlap} px',
                        'expected': '比例尺与图框之间应有间距',
                        'suggestion': ('比例尺覆盖了主图框边框。在GMT中调整 '
                                       'gmt basemap -Lj 或 inset 的偏移参数，'
                                       '将比例尺移离图框边框。也可使用 +o<offset> 参数。'),
                        'priority': 'high',
                    })
                else:
                    gap = sb_y0 - fy1 if sb_y0 > fy1 else fy0 - sb_y1
                    self.passes.append(
                        f'比例尺未覆盖图框边框 (间距 {max(0, gap):.0f} px)')
                return

        print("  No scale bar detected")

    # -----------------------------------------------------------------------
    # Cross-validation: compare detected elements against plan expectations
    # -----------------------------------------------------------------------

    def cross_validate(self):
        """Cross-validate detected elements against plan expectations.

        Flags mismatches:
        - Plan expects a legend but none detected → ❌ failure
        - Plan expects a colorbar but none detected → ❌ failure
        - Plan expects a scale bar but none detected → ⚠️ warning
        - Plan does NOT expect a legend but one was detected → ⚠️ warning
        """
        if not self.plan_info or not self.plan_path:
            return

        print("\n[10/10] Cross-validating against plan expectations ...")

        # Colorbar check
        if self.plan_info.get('expects_colorbar') and not self.colorbar_bounds:
            self.failures.append({
                'item': '计划要求色标但未检测到',
                'current': '未发现色标条',
                'expected': '图件中应有色标（colorbar）',
                'suggestion': ('绘图计划中要求绘制色标，但脚本未能检测到。'
                               '请确认色标是否已在 GMT 脚本中正确配置并执行。'
                               '检查 gmt colorbar 命令及其参数。'),
                'priority': 'high',
            })

        # Legend check
        if self.plan_info.get('expects_legend') and not self.legend_bounds:
            self.failures.append({
                'item': '计划要求图例但未检测到',
                'current': '未发现图例框',
                'expected': '图件中应有图例（legend）',
                'suggestion': ('绘图计划中要求绘制图例，但脚本未能检测到。'
                               '请确认图例是否已在 GMT 脚本中正确配置并执行。'
                               '检查 gmt legend 命令及其参数。'),
                'priority': 'high',
            })

        # Scale bar check
        if self.plan_info.get('expects_scale_bar') and not getattr(self, '_scale_bar_detected', False):
            self.warnings.append({
                'item': '计划要求比例尺但未检测到',
                'current': '未发现比例尺',
                'suggested': '图件中应有比例尺（scale bar）',
                'suggestion': ('绘图计划中要求绘制比例尺，但脚本未能检测到。'
                               '请确认 gmt basemap -L 参数是否正确配置。'),
                'priority': 'medium',
            })

        # Report cross-validation result
        checks = []
        if self.plan_info.get('expects_colorbar'):
            checks.append(f"色标: {'✅' if self.colorbar_bounds else '❌'}")
        if self.plan_info.get('expects_legend'):
            checks.append(f"图例: {'✅' if self.legend_bounds else '❌'}")
        if self.plan_info.get('expects_scale_bar'):
            checks.append(f"比例尺: {'✅' if getattr(self, '_scale_bar_detected', False) else '❌'}")
        if checks:
            print(f"  Cross-validation: {'  '.join(checks)}")
        else:
            print("  No plan expectations to validate against")

    # -----------------------------------------------------------------------
    # Report generation
    # -----------------------------------------------------------------------

    def generate_report(self, output_path):
        """Generate structured markdown verification report."""
        print(f"\nGenerating report: {output_path}")
        r = []

        def w(line):
            r.append(line)

        w("## 图件布局校验报告\n")
        w("### 基本信息\n")
        w(f"- 校验图件: `{self.image_path}`")
        w(f"- 图件尺寸: {self.width}x{self.height} px")
        w(f"- 最小间距阈值: {self.min_gap} px")
        w(f"- 校验时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if self.plan_path:
            w(f"- 绘图计划: `{self.plan_path}`")
        w("")

        # Plan expectations summary
        if self.plan_info and self.plan_path:
            w("### 计划预期 vs 检测结果\n")
            w("| 元素 | 计划预期 | 检测结果 | 位置/尺寸 |")
            w("|------|----------|----------|-----------|")
            # Main frame
            if self.frame_bounds:
                x0, y0, x1, y1 = self.frame_bounds
                w(f"| 主图框 | ✅ 预期 | ✅ | ({x0},{y0})-({x1},{y1}), {x1 - x0}x{y1 - y0}px |")
            # Colorbar
            cb_expected = '✅ 预期' if self.plan_info.get('expects_colorbar') else '—'
            if self.colorbar_bounds:
                c = self.colorbar_bounds
                w(f"| 色标 | {cb_expected} | ✅ ({self.colorbar_side}侧) | ({c[0]},{c[1]})-({c[2]},{c[3]}), {c[2] - c[0]}x{c[3] - c[1]}px |")
            else:
                cb_status = '❌ 缺失' if self.plan_info.get('expects_colorbar') else '— 跳过'
                w(f"| 色标 | {cb_expected} | {cb_status} | — |")
            # Legend
            lg_expected = '✅ 预期' if self.plan_info.get('expects_legend') else '—'
            if self.legend_bounds:
                l = self.legend_bounds
                w(f"| 图例 | {lg_expected} | ✅ | ({l[0]},{l[1]})-({l[2]},{l[3]}), {l[2] - l[0]}x{l[3] - l[1]}px |")
            else:
                lg_status = '❌ 缺失' if self.plan_info.get('expects_legend') else '— 跳过'
                w(f"| 图例 | {lg_expected} | {lg_status} | — |")
            # Scale bar
            sb_expected = '✅ 预期' if self.plan_info.get('expects_scale_bar') else '—'
            sb_found = getattr(self, '_scale_bar_detected', False)
            if sb_found:
                w(f"| 比例尺 | {sb_expected} | ✅ | — |")
            else:
                sb_status = '❌ 缺失' if self.plan_info.get('expects_scale_bar') else '— 跳过'
                w(f"| 比例尺 | {sb_expected} | {sb_status} | — |")
            w("")
        else:
            # Legacy element detection table (no plan)
            w("### 元素检测结果\n")
            w("| 元素 | 状态 | 位置/尺寸 |")
            w("|------|------|-----------|")
            if self.frame_bounds:
                x0, y0, x1, y1 = self.frame_bounds
                w(f"| 主图框 | ✅ | ({x0},{y0})-({x1},{y1}), {x1 - x0}x{y1 - y0}px |")
            else:
                w("| 主图框 | ❌ | - |")
            if self.colorbar_bounds:
                c = self.colorbar_bounds
                w(f"| 色标 | ✅ ({self.colorbar_side}侧) | ({c[0]},{c[1]})-({c[2]},{c[3]}), {c[2] - c[0]}x{c[3] - c[1]}px |")
            else:
                w("| 色标 | ⚠️ | 未检测到 |")
            if self.legend_bounds:
                l = self.legend_bounds
                w(f"| 图例 | ✅ | ({l[0]},{l[1]})-({l[2]},{l[3]}), {l[2] - l[0]}x{l[3] - l[1]}px |")
            else:
                w("| 图例 | ⚠️ | 未检测到 |")
            w("")

        # Gap summary
        w("### 间距检测结果\n")
        w("| 检测项 | 状态 | 详情 |")
        w("|--------|------|------|")
        if self._colorbar_gap is not None:
            s = "✅" if self._colorbar_gap >= self.min_gap else "❌"
            w(f"| 色标与主图框间距 | {s} | {self._colorbar_gap:.0f} px (阈值: {self.min_gap} px) |")
        else:
            w("| 色标与主图框间距 | ⚠️ | 未检测到色标 |")
        if self._legend_distances:
            md = min(self._legend_distances.values())
            s = "✅" if md >= 5 else "⚠️"
            w(f"| 图例与主图间距 | {s} | 最小 {md:.0f} px |")
        else:
            w("| 图例与主图间距 | ⚠️ | 未检测到图例 |")
        if hasattr(self, '_legend_density'):
            s = "✅" if self._legend_percentile < 40 else "⚠️"
            w(f"| 图例位置合理性 | {s} | 密度 {self._legend_density:.3f} (百分位 {self._legend_percentile:.0f}%) |")
        else:
            w("| 图例位置合理性 | ⚠️ | 未检测到图例 |")
        w("")

        # Failures
        if self.failures:
            w("### ❌ 不合格项 (必须修复)\n")
            for i, f in enumerate(self.failures, 1):
                w(f"**{i}. {f['item']}**\n")
                w(f"- 当前值: {f['current']}")
                w(f"- 期望值: {f['expected']}")
                w(f"- 修改建议: {f['suggestion']}\n")
        else:
            w("### ❌ 不合格项\n\n无不合格项。\n")

        # Warnings
        if self.warnings:
            w("### ⚠️ 需改进项\n")
            for i, f in enumerate(self.warnings, 1):
                w(f"**{i}. {f['item']}**\n")
                w(f"- 当前值: {f['current']}")
                w(f"- 建议值: {f['suggested']}")
                w(f"- 优化建议: {f['suggestion']}\n")
        else:
            w("### ⚠️ 需改进项\n\n无需改进项。\n")

        # Passes
        if self.passes:
            w("### ✅ 合格项\n")
            for p in self.passes:
                w(f"- {p}")
            w("")

        # Priority
        all_issues = [(x, x.get('priority', 'medium')) for x in self.failures + self.warnings]
        all_issues.sort(key=lambda x: {'high': 0, 'medium': 1, 'low': 2}.get(x[1], 99))
        if all_issues:
            w("### 修复优先级建议\n")
            for i, (issue, pri) in enumerate(all_issues, 1):
                tag = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(pri, '⚪')
                w(f"{i}. [{tag}] {issue['item']}")
            w("")

        # Density visualization
        if self.info_density_map_norm is not None:
            w("### 信息密度分析\n")
            w(f"主图区域划分为 {self.info_density_map_norm.shape[0]}x{self.info_density_map_norm.shape[1]} 网格：\n")
            w("```")
            for row in self.info_density_map_norm:
                w(' '.join('·▏▎▍▌▋▊▉█'[min(int(v * 8), 8)] for v in row))
            w("```")
            if hasattr(self, '_corners'):
                w("\n四角密度：")
                for corner, d in self._corners.items():
                    w(f"- {corner}: {d:.3f}")
                w(f"\n最佳图例位置: {self._best_corner}\n")

        text = '\n'.join(r)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Report saved: {output_path}")
        return text

    # -----------------------------------------------------------------------
    # Main
    # -----------------------------------------------------------------------

    def run(self):
        self.detect_main_frame()
        self.detect_colorbar()
        self.detect_legend()
        self.analyze_info_density()
        self.measure_gaps()
        self.detect_overlaps()
        self.check_colorbar_details()
        self.check_legend_details()
        self.detect_scale_bar()
        self.cross_validate()
        return self


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GMT figure layout verification (OpenCV)")
    parser.add_argument("image", help="Path to figure (png/jpg)")
    parser.add_argument("--output", default="verify_report.md", help="Report output path")
    parser.add_argument("--output-dir", default=".", help="Output directory")
    parser.add_argument("--plan", default=None, help="Plotting plan file (optional)")
    parser.add_argument("--threshold", type=int, default=2, help="Min gap pixels (default: 2)")
    parser.add_argument("--ratio", type=float, default=0.005,
                        help="Min gap as ratio of short side (default: 0.005)")
    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(f"Error: image not found: {args.image}")
        sys.exit(1)
    if args.plan and not os.path.exists(args.plan):
        print(f"Warning: plan not found: {args.plan}, continuing without plan")

    out_dir = Path(args.output_dir).resolve()
    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = out_dir / args.output

    verifier = PlotVerifier(args.image, args.threshold, args.ratio, args.plan)
    verifier.run()
    verifier.generate_report(str(out_path))

    print("\n" + "=" * 60)
    print("Verification Summary")
    print("=" * 60)
    print(f"Failures:  {len(verifier.failures)}")
    print(f"Warnings:  {len(verifier.warnings)}")
    print(f"Passed:    {len(verifier.passes)}")
    for f in verifier.failures:
        print(f"  ❌ {f['item']}: {f['current']}")
    for w in verifier.warnings:
        print(f"  ⚠️ {w['item']}: {w['current']}")


if __name__ == "__main__":
    main()
