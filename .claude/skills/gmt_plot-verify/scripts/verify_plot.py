#!/usr/bin/env python3
"""
Simplified GMT figure layout verification script.

Checks (plan-driven, only for elements mentioned in plan.md):
  1. Whether legend/colorbar/scale bar overlap the main frame border
  2. Whether components are placed in high data-density areas

Usage:
    python verify_plot.py <image_path> --plan plan.md [--output REPORT.md]

Dependencies:
    pip install opencv-python-headless numpy Pillow
"""

import argparse, os, re, sys
from pathlib import Path
from datetime import datetime
import numpy as np
from PIL import Image

try:
    import cv2
except ImportError:
    print("Error: opencv-python-headless is required. pip install opencv-python-headless")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _longest_run(mask):
    """Longest consecutive True run in a boolean array."""
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


# ---------------------------------------------------------------------------
# Main verifier
# ---------------------------------------------------------------------------

class PlotVerifier:
    """Analyze a GMT plot for frame-border overlaps and density placement."""

    def __init__(self, image_path, plan_path=None):
        self.image_path = image_path
        self.plan_path = plan_path
        self.img_pil = Image.open(image_path).convert('RGB')
        self.width, self.height = self.img_pil.size
        self.short_side = min(self.width, self.height)

        self.bgr = np.array(self.img_pil)[:, :, ::-1]
        self.gray = cv2.cvtColor(self.bgr, cv2.COLOR_BGR2GRAY)

        self.frame_bounds = None        # (x0, y0, x1, y1)
        self.colorbar_bounds = None     # (x0, y0, x1, y1)
        self.colorbar_side = None       # 'right', 'bottom', 'left'
        self.legend_bounds = None       # (x0, y0, x1, y1)
        self.scale_bar_bounds = None    # (x0, y0, x1, y1)
        self.info_density_map_norm = None  # 8x8 normalized density grid

        self.plan_info = {'expects_colorbar': False, 'expects_legend': False,
                          'expects_scale_bar': False}
        self._parse_plan()

        self.failures = []
        self.warnings = []
        self.passes = []

        print(f"Image loaded: {self.width}x{self.height} px")

    # -------------------------------------------------------------------
    # Plan parsing
    # -------------------------------------------------------------------

    def _parse_plan(self):
        """Parse plan.md to determine which elements are expected."""
        if not self.plan_path or not os.path.exists(self.plan_path):
            self.plan_info = {'expects_colorbar': True, 'expects_legend': True,
                              'expects_scale_bar': True}
            print("  No plan file; detecting all elements.")
            return

        with open(self.plan_path, 'r', encoding='utf-8') as f:
            text = f.read()

        if re.search(r'(colorbar|色标|颜色条|颜色标)', text, re.IGNORECASE):
            self.plan_info['expects_colorbar'] = True
        if re.search(r'(legend\b|图例)', text, re.IGNORECASE):
            self.plan_info['expects_legend'] = True
        if re.search(r'(比例尺|scale\s*bar|scalebar)', text, re.IGNORECASE):
            self.plan_info['expects_scale_bar'] = True

        print(f"  Plan expects: colorbar={'yes' if self.plan_info['expects_colorbar'] else 'no'}, "
              f"legend={'yes' if self.plan_info['expects_legend'] else 'no'}, "
              f"scale_bar={'yes' if self.plan_info['expects_scale_bar'] else 'no'}")

    # -------------------------------------------------------------------
    # Step 1: Main frame detection (content-boundary method)
    # -------------------------------------------------------------------

    def detect_main_frame(self):
        """Detect main plot frame by scanning inward for non-white content."""
        print("\n[1] Detecting main frame ...")
        h, w = self.gray.shape
        WHITE_THRESH = 250
        max_search_v = int(h * 0.35)
        max_search_h = int(w * 0.35)

        def _find_edge_row(start, end, step):
            for y in range(start, end, step):
                row = self.gray[y, :]
                nw = row < WHITE_THRESH
                runs = np.diff(np.where(np.concatenate([[False], nw, [False]]))[0])[::2]
                if np.any(runs >= w * 0.15):
                    return y
                if np.mean(nw) >= 0.01:
                    return y
            return None

        def _find_edge_col(start, end, step):
            for x in range(start, end, step):
                col = self.gray[:, x]
                nw = col < WHITE_THRESH
                runs = np.diff(np.where(np.concatenate([[False], nw, [False]]))[0])[::2]
                if np.any(runs >= h * 0.15):
                    return x
                if np.mean(nw) >= 0.01:
                    return x
            return None

        top = _find_edge_row(0, max_search_v, 1)
        bottom = _find_edge_row(h - 1, h - max_search_v - 1, -1)
        left = _find_edge_col(0, max_search_h, 1)
        right = _find_edge_col(w - 1, w - max_search_h - 1, -1)

        if top is not None and bottom is not None and left is not None and right is not None \
                and top < bottom and left < right:
            self.frame_bounds = (left, top, right, bottom)
        else:
            m = int(self.short_side * 0.05)
            self.frame_bounds = (m, m, w - m - 1, h - m - 1)
            print("  Warning: using fallback frame bounds")

        fx0, fy0, fx1, fy1 = self.frame_bounds
        print(f"  Main frame: ({fx0},{fy0})-({fx1},{fy1}), {fx1-fx0}x{fy1-fy0} px")

    # -------------------------------------------------------------------
    # Step 2: Colorbar detection (gradient-based)
    # -------------------------------------------------------------------

    def detect_colorbar(self):
        """Detect colorbar using gradient analysis outside the main frame."""
        print("\n[2] Detecting colorbar ...")
        if not self.plan_info.get('expects_colorbar'):
            print("  Skipped: plan does not mention colorbar")
            return

        fx0, fy0, fx1, fy1 = self.frame_bounds
        fw, fh = fx1 - fx0, fy1 - fy0

        regions = [
            ('right',  (fx1, fy0, self.width, fy1)),
            ('bottom', (fx0, fy1, fx1, self.height)),
            ('left',   (0, fy0, fx0, fy1)),
        ]

        best = None
        for side, (rx0, ry0, rx1, ry1) in regions:
            if rx1 - rx0 <= 10 or ry1 - ry0 <= 10:
                continue
            r = self._search_colorbar(side, rx0, ry0, rx1, ry1, fw, fh)
            if r and (best is None or r['confidence'] > best['confidence']):
                best = r

        if best and best['confidence'] >= 0.25:
            self.colorbar_bounds = best['bounds']
            self.colorbar_side = best['side']
            cb = self.colorbar_bounds
            print(f"  Colorbar on {best['side']}: ({cb[0]},{cb[1]})-({cb[2]},{cb[3]}), "
                  f"conf={best['confidence']:.2f}")
        else:
            print(f"  No colorbar detected (best conf: {best['confidence']:.2f})" if best
                  else "  No colorbar detected")

    def _search_colorbar(self, side, rx0, ry0, rx1, ry1, fw, fh):
        """Search for colorbar in a region using gradient analysis."""
        region = self.bgr[ry0:ry1, rx0:rx1]
        rh, rw = region.shape[:2]
        if rh < 5 or rw < 5:
            return None

        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

        if side in ('right', 'left'):
            grad = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            grad_mag = np.abs(grad)
            col_grad = np.mean(grad_mag, axis=0)
            if col_grad.max() > 0:
                col_grad /= col_grad.max()
            mask = (col_grad > 0.03) & (col_grad < 0.85)
            best_start, best_len = _longest_run(mask)
            if best_len < 4:
                return None
            cb_x0 = rx0 + best_start
            cb_x1 = rx0 + best_start + best_len
            bar_cols = grad_mag[:, best_start:best_start + best_len]
            row_grad = np.mean(bar_cols, axis=1)
            thresh = np.mean(row_grad) * 0.3 if np.mean(row_grad) > 0 else 0
            active = np.where(row_grad > thresh)[0]
            cb_y0 = ry0 + (active[0] if len(active) > 0 else 0)
            cb_y1 = ry0 + (active[-1] + 1 if len(active) > 0 else rh)
            bar_long = cb_y1 - cb_y0
            frame_dim = fh
        else:
            grad = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            grad_mag = np.abs(grad)
            row_grad = np.mean(grad_mag, axis=1)
            if row_grad.max() > 0:
                row_grad /= row_grad.max()
            mask = (row_grad > 0.03) & (row_grad < 0.85)
            best_start, best_len = _longest_run(mask)
            if best_len < 4:
                return None
            cb_y0 = ry0 + best_start
            cb_y1 = ry0 + best_start + best_len
            bar_rows = grad_mag[best_start:best_start + best_len, :]
            col_grad = np.mean(bar_rows, axis=0)
            thresh = np.mean(col_grad) * 0.3 if np.mean(col_grad) > 0 else 0
            active = np.where(col_grad > thresh)[0]
            cb_x0 = rx0 + (active[0] if len(active) > 0 else 0)
            cb_x1 = rx0 + (active[-1] + 1 if len(active) > 0 else rw)
            bar_long = cb_x1 - cb_x0
            frame_dim = fw

        cb_w, cb_h = cb_x1 - cb_x0, cb_y1 - cb_y0
        if cb_w < 3 or cb_h < 10:
            return None
        if side in ('right', 'left') and cb_w > self.width * 0.15:
            return None
        if side == 'bottom' and cb_h > self.height * 0.15:
            return None

        length_ratio = bar_long / max(frame_dim, 1)
        aspect_score = 1.0 if 0.4 <= length_ratio <= 1.05 else max(0, length_ratio / 0.4)
        confidence = 0.6 * aspect_score + 0.4

        return {'bounds': (cb_x0, cb_y0, cb_x1, cb_y1), 'side': side, 'confidence': confidence}

    # -------------------------------------------------------------------
    # Step 3: Legend detection (contour-based)
    # -------------------------------------------------------------------

    def detect_legend(self):
        """Detect legend box using contour analysis inside the main frame."""
        print("\n[3] Detecting legend ...")
        if not self.plan_info.get('expects_legend'):
            print("  Skipped: plan does not mention legend")
            return

        fx0, fy0, fx1, fy1 = self.frame_bounds
        fw, fh = fx1 - fx0, fy1 - fy0
        margin = int(min(fw, fh) * 0.12)

        sx0 = max(0, fx0 - margin)
        sy0 = max(0, fy0 - margin)
        sx1 = min(self.width, fx1 + margin)
        sy1 = min(self.height, fy1 + margin)

        search_region = self.bgr[sy0:sy1, sx0:sx1]
        search_gray = cv2.cvtColor(search_region, cv2.COLOR_BGR2GRAY)

        edges = cv2.Canny(search_gray, 40, 120)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges_closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=1)

        contours, _ = cv2.findContours(edges_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        frame_area = fw * fh
        best = None
        best_score = 0

        for cnt in contours:
            x, y, w_rect, h_rect = cv2.boundingRect(cnt)
            area = w_rect * h_rect
            if area < 0.003 * frame_area or area > 0.35 * frame_area:
                continue

            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            if len(approx) < 4 or len(approx) > 12:
                continue

            aspect = h_rect / max(w_rect, 1)
            if aspect > 8 or aspect < 0.25:
                continue

            roi = search_gray[y:y + h_rect, x:x + w_rect]
            mean_brightness = np.mean(roi)
            if mean_brightness < 140:
                continue

            # Border score
            border_score = self._border_score(edges, x, y, w_rect, h_rect)
            min_border = 0.25 if area < 0.10 * frame_area else 0.40
            if border_score < min_border:
                continue

            cnt_area = cv2.contourArea(cnt)
            rectangularity = cnt_area / area if area > 0 else 0
            score = 0.35 * border_score + 0.25 * (mean_brightness / 255.0) + \
                    0.40 * rectangularity

            if score > best_score:
                best_score = score
                best = (sx0 + x, sy0 + y, sx0 + x + w_rect, sy0 + y + h_rect)

        if best and best_score > 0.35:
            self.legend_bounds = best
            lb = self.legend_bounds
            print(f"  Legend: ({lb[0]},{lb[1]})-({lb[2]},{lb[3]}), score={best_score:.2f}")
        else:
            print("  No legend detected")

    @staticmethod
    def _border_score(edges, x, y, w, h_rect):
        """Fraction of rectangle perimeter aligned with edge pixels."""
        eh, ew = edges.shape
        y2, x2 = min(y + h_rect - 1, eh - 1), min(x + w - 1, ew - 1)
        top = edges[y, x:min(x + w, ew)]
        bot = edges[y2, x:min(x + w, ew)]
        left = edges[y:min(y + h_rect, eh), x]
        right = edges[y:min(y + h_rect, eh), x2]
        total = 2 * (w + h_rect)
        if total == 0:
            return 0
        hits = np.sum(top > 0) + np.sum(bot > 0) + np.sum(left > 0) + np.sum(right > 0)
        return min(hits / (total * 0.4), 1.0)

    # -------------------------------------------------------------------
    # Step 4: Scale bar detection
    # -------------------------------------------------------------------

    def detect_scale_bar(self):
        """Detect scale bar (alternating dark/light segments) near frame bottom."""
        print("\n[4] Detecting scale bar ...")
        if not self.plan_info.get('expects_scale_bar'):
            print("  Skipped: plan does not mention scale bar")
            return

        fx0, fy0, fx1, fy1 = self.frame_bounds
        fh = fy1 - fy0
        fw = fx1 - fx0

        search_y0 = fy1 - int(fh * 0.08)
        search_y1 = min(fy1 + int(fh * 0.25), self.height)
        search_x0 = fx0 + int(fw * 0.1)
        search_x1 = fx1 - int(fw * 0.1)

        if search_y1 - search_y0 < 10 or search_x1 - search_x0 < 20:
            print("  Search region too small")
            return

        roi = self.gray[search_y0:search_y1, search_x0:search_x1]
        rh, rw = roi.shape
        if rw < 20:
            return

        grad_x = cv2.Sobel(roi, cv2.CV_64F, 1, 0, ksize=3)
        grad_mag = np.abs(grad_x)
        row_grad = np.mean(grad_mag, axis=1)
        if row_grad.max() > 0:
            row_grad_norm = row_grad / row_grad.max()

        active_rows = np.where(row_grad_norm > 0.15)[0]
        if len(active_rows) < 3:
            print("  No scale bar detected")
            return

        groups = self._group_vals(active_rows, gap=5)
        for g in groups:
            if len(g) < 3:
                continue
            sb_y0 = search_y0 + g[0]
            sb_y1 = search_y0 + g[-1] + 1
            col_grad = np.mean(grad_mag[g[0]:g[-1] + 1, :], axis=0)
            if col_grad.max() <= 0:
                continue
            col_grad_norm = col_grad / col_grad.max()
            active_cols = np.where(col_grad_norm > 0.15)[0]
            if len(active_cols) < 5:
                continue
            col_groups = self._group_vals(active_cols, gap=20)
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
                self.scale_bar_bounds = (sb_x0, sb_y0, sb_x1, sb_y1)
                print(f"  Scale bar: ({sb_x0},{sb_y0})-({sb_x1},{sb_y1}), {sb_w}x{sb_h} px")
                return

        print("  No scale bar detected")

    @staticmethod
    def _group_vals(values, gap=30):
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

    # -------------------------------------------------------------------
    # Step 5: Information density analysis
    # -------------------------------------------------------------------

    def analyze_info_density(self):
        """8x8 grid analysis of data density inside the main frame."""
        print("\n[5] Analyzing information density ...")
        fx0, fy0, fx1, fy1 = self.frame_bounds
        interior = self.gray[fy0:fy1, fx0:fx1]
        fh, fw = interior.shape

        grid_size = 8
        h_step = max(fh // grid_size, 1)
        w_step = max(fw // grid_size, 1)
        gh, gw = fh // h_step, fw // w_step

        density = np.zeros((gh, gw), dtype=np.float32)
        for gy in range(gh):
            for gx in range(gw):
                y0, y1 = gy * h_step, min((gy + 1) * h_step, fh)
                x0, x1 = gx * w_step, min((gx + 1) * w_step, fw)
                cell = interior[y0:y1, x0:x1]
                if cell.size > 0:
                    color_var = np.var(cell.astype(np.float64))
                    gy_edge = cv2.Sobel(cell, cv2.CV_64F, 0, 1, ksize=3)
                    gx_edge = cv2.Sobel(cell, cv2.CV_64F, 1, 0, ksize=3)
                    edge_density = np.mean(np.sqrt(gy_edge ** 2 + gx_edge ** 2))
                    density[gy, gx] = color_var * 0.6 + edge_density * 0.4

        v_min, v_max = density.min(), density.max()
        self.info_density_map_norm = ((density - v_min) / (v_max - v_min)
                                      if v_max > v_min else np.zeros_like(density))
        print(f"  Density grid: {gh}x{gw}, range [{v_min:.1f}, {v_max:.1f}]")

    # -------------------------------------------------------------------
    # Step 6: Frame border overlap check
    # -------------------------------------------------------------------

    def check_frame_overlaps(self):
        """Check if any component overlaps the main frame border."""
        print("\n[6] Checking frame border overlaps ...")
        fx0, fy0, fx1, fy1 = self.frame_bounds
        frame_margin = 3  # px tolerance for frame line + ticks

        checks = []
        if self.legend_bounds:
            checks.append(('图例', self.legend_bounds))
        if self.colorbar_bounds:
            checks.append(('色标', self.colorbar_bounds))
        if self.scale_bar_bounds:
            checks.append(('比例尺', self.scale_bar_bounds))

        for name, (cx0, cy0, cx1, cy1) in checks:
            overlaps = []
            if cx0 < fx0 + frame_margin and cx1 > fx0:
                overlaps.append(('左边框', cx0 - fx0))
            if cx1 > fx1 - frame_margin and cx0 < fx1:
                overlaps.append(('右边框', cx1 - fx1))
            if cy0 < fy0 + frame_margin and cy1 > fy0:
                overlaps.append(('上边框', cy0 - fy0))
            if cy1 > fy1 - frame_margin and cy0 < fy1:
                overlaps.append(('下边框', cy1 - fy1))

            if overlaps:
                detail = '; '.join(f'{e}({v:+d}px)' for e, v in overlaps)
                self.failures.append({
                    'item': f'{name}覆盖主图框边框',
                    'current': f'与 {detail}',
                    'expected': f'{name}与图框边框之间应留有间距',
                    'suggestion': (f'{name}与主图框边框重叠。请调整 GMT 参数中'
                                   f'{name}的偏移量（如 -D 或 +o 参数），'
                                   f'使{name}与图框保持间距。'),
                    'priority': 'high',
                })
                print(f"  ❌ {name} overlaps frame: {detail}")
            else:
                self.passes.append(f'{name}未覆盖主图框边框')
                print(f"  ✅ {name}: no overlap")

        if not checks:
            self.passes.append('无组件需要检查（plan 未预期任何组件）')

    # -------------------------------------------------------------------
    # Step 7: Density placement check
    # -------------------------------------------------------------------

    def check_density_placement(self):
        """Check if components are placed in high-density areas."""
        print("\n[7] Checking density placement ...")
        if self.info_density_map_norm is None:
            print("  No density map available")
            return

        fx0, fy0, _, _ = self.frame_bounds
        fh, fw = (self.frame_bounds[3] - self.frame_bounds[1],
                   self.frame_bounds[2] - self.frame_bounds[0])
        h_step = fh / self.info_density_map_norm.shape[0]
        w_step = fw / self.info_density_map_norm.shape[1]
        all_density = self.info_density_map_norm.flatten()

        checks = []
        if self.legend_bounds:
            checks.append(('图例', self.legend_bounds))
        if self.colorbar_bounds:
            checks.append(('色标', self.colorbar_bounds))
        if self.scale_bar_bounds:
            checks.append(('比例尺', self.scale_bar_bounds))

        HIGH_THRESH = 0.65  # density percentile above which placement is questionable

        for name, (cx0, cy0, cx1, cy1) in checks:
            # Map component center to density grid
            cx = (cx0 + cx1) / 2
            cy = (cy0 + cy1) / 2
            gx = int(np.clip((cx - fx0) / w_step, 0, self.info_density_map_norm.shape[1] - 1))
            gy = int(np.clip((cy - fy0) / h_step, 0, self.info_density_map_norm.shape[0] - 1))
            cell_density = float(self.info_density_map_norm[gy, gx])
            percentile = float(np.sum(all_density <= cell_density) / len(all_density) * 100)

            if percentile > 80:
                self.failures.append({
                    'item': f'{name}放置在数据高密度区域',
                    'current': f'密度百分位 {percentile:.0f}%（网格 [{gy},{gx}]）',
                    'expected': f'百分位 <= {HIGH_THRESH * 100:.0f}%（放在数据稀疏区）',
                    'suggestion': (f'{name}放在数据密集区域，可能遮挡重要内容。'
                                   f'请将{name}移至密度更低的角落或边缘位置。'),
                    'priority': 'high',
                })
            elif percentile > HIGH_THRESH * 100:
                self.warnings.append({
                    'item': f'{name}放置在数据中等密度区域',
                    'current': f'密度百分位 {percentile:.0f}%（网格 [{gy},{gx}]）',
                    'suggested': f'百分位 <= {HIGH_THRESH * 100:.0f}%',
                    'suggestion': (f'{name}所在位置数据密度偏高，建议移至更稀疏的'
                                   f'区域以避免遮挡。'),
                    'priority': 'medium',
                })
            else:
                self.passes.append(f'{name}放置在数据稀疏区域（百分位 {percentile:.0f}%）')

            tag = '✅' if percentile <= HIGH_THRESH * 100 else '❌' if percentile > 80 else '⚠️'
            print(f"  {tag} {name}: density={cell_density:.3f}, percentile={percentile:.0f}%")

        # Report best corner for placement
        if self.info_density_map_norm is not None:
            corners = {
                '左上角': self.info_density_map_norm[0, 0],
                '右上角': self.info_density_map_norm[0, -1],
                '左下角': self.info_density_map_norm[-1, 0],
                '右下角': self.info_density_map_norm[-1, -1],
            }
            best = min(corners, key=corners.get)
            print(f"  Suggested best corner: {best} (density={corners[best]:.3f})")
            self._best_corner = best
            self._corners = corners

    # -------------------------------------------------------------------
    # Report generation
    # -------------------------------------------------------------------

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
        w(f"- 校验时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if self.plan_path:
            w(f"- 绘图计划: `{self.plan_path}`")
        w("")

        # Detection summary
        w("### 元素检测结果\n")
        w("| 元素 | 计划预期 | 检测结果 |")
        w("|------|----------|----------|")
        cb_found = self.colorbar_bounds is not None
        w(f"| 色标 | {'✅' if self.plan_info['expects_colorbar'] else '—'} | "
          f"{'✅' if cb_found else '❌ 未检测到'} |")
        lg_found = self.legend_bounds is not None
        w(f"| 图例 | {'✅' if self.plan_info['expects_legend'] else '—'} | "
          f"{'✅' if lg_found else '❌ 未检测到'} |")
        sb_found = self.scale_bar_bounds is not None
        w(f"| 比例尺 | {'✅' if self.plan_info['expects_scale_bar'] else '—'} | "
          f"{'✅' if sb_found else '❌ 未检测到'} |")
        w("")

        # 检查一：边框覆盖
        w("### 检查一：组件是否覆盖主图框边框\n")
        frame_overlap_items = [f for f in self.failures if '边框' in f['item'] or '覆盖' in f['item']]
        if frame_overlap_items:
            for item in frame_overlap_items:
                w(f"- ❌ **{item['item']}**: {item['current']}")
                w(f"  - 建议: {item['suggestion']}")
        else:
            w("✅ 所有组件均未覆盖主图框边框")
        w("")

        # 检查二：密度放置
        w("### 检查二：组件是否放置在数据高密度区域\n")
        density_items = [f for f in self.failures + self.warnings
                         if '密度' in f['item']]
        if density_items:
            for item in density_items:
                tag = '❌' if item in self.failures else '⚠️'
                w(f"- {tag} **{item['item']}**: {item['current']}")
                w(f"  - 建议: {item['suggestion']}")
        else:
            w("✅ 所有组件均放置在数据稀疏区域")
        w("")

        # Density visualization
        if self.info_density_map_norm is not None:
            w("### 主图框信息密度分布（8×8 网格）\n")
            w("```")
            for row in self.info_density_map_norm:
                w(' '.join('·▏▎▍▌▋▊▉█'[min(int(v * 8), 8)] for v in row))
            w("```")
            if hasattr(self, '_corners'):
                w("\n四角密度：")
                for corner, d in self._corners.items():
                    w(f"- {corner}: {d:.3f}")
                w(f"\n建议放置位置: **{self._best_corner}**\n")

        text = '\n'.join(r)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Report saved: {output_path}")
        return text

    # -------------------------------------------------------------------
    # Run
    # -------------------------------------------------------------------

    def run(self):
        self.detect_main_frame()
        self.detect_colorbar()
        self.detect_legend()
        self.detect_scale_bar()
        self.analyze_info_density()
        self.check_frame_overlaps()
        self.check_density_placement()
        return self


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GMT figure layout verification")
    parser.add_argument("image", help="Path to figure (png/jpg)")
    parser.add_argument("--plan", default=None, help="Plot plan file (plan.md)")
    parser.add_argument("--output", default="verify_report.md", help="Report output path")
    parser.add_argument("--output-dir", default=".", help="Output directory")
    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(f"Error: image not found: {args.image}")
        sys.exit(1)

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = Path(args.output_dir).resolve() / args.output

    verifier = PlotVerifier(args.image, args.plan)
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
