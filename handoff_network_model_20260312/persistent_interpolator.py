from typing import Union, Iterable
import os, json, numpy as np, pandas as pd
from dataclasses import dataclass

CACHE_SUFFIX = '.interp_cache.npz'
META_SUFFIX = '.interp_cache.meta.json'

from typing import Tuple
def _file_sig(path: str) -> Tuple[int, int]:
    st = os.stat(path)
    return (st.st_size, getattr(st, 'st_mtime_ns', int(st.st_mtime * 1e9)))

@dataclass
class CacheMeta:
    source_path: str
    source_size: int
    source_mtime_ns: int
    x_min: float
    x_max: float
    n: int

def _write_meta(meta_path: str, meta: CacheMeta) -> None:
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta.__dict__, f, ensure_ascii=False, indent=2)

def _read_meta(meta_path: str) -> CacheMeta:
    with open(meta_path, 'r', encoding='utf-8') as f:
        d = json.load(f)
    return CacheMeta(**d)

def _clean_xy_from_csv(csv_path: str):
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]
    cols = df.columns.tolist()
    def pick(name_candidates, fallback_idx):
        for c in name_candidates:
            if c in cols:
                return c
        return cols[fallback_idx]
    x_col = pick(['x','time','t'], 0)
    y_col = pick(['y','value','val'], 1 if len(cols) > 1 else 0)
    x = pd.to_numeric(df[x_col], errors='coerce').to_numpy()
    y = pd.to_numeric(df[y_col], errors='coerce').to_numpy()
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]
    idx = np.argsort(x, kind='mergesort')
    x = x[idx]
    y = y[idx]
    dedup_df = pd.DataFrame({'x': x, 'y': y}).drop_duplicates(subset='x', keep='last').sort_values('x')
    x = dedup_df['x'].to_numpy(dtype=float)
    y = dedup_df['y'].to_numpy(dtype=float)
    return x, y

def _save_cache(cache_path: str, x, y) -> None:
    import numpy as _np
    _np.savez(cache_path, x=x, y=y)

def _load_cache(cache_path: str):
    import numpy as _np
    with _np.load(cache_path) as npz:
        return npz['x'], npz['y']

class PersistentLinearInterpolator:
    def __init__(self, csv_path: str, allow_extrapolation: bool=False):
        self.csv_path = os.path.abspath(csv_path)
        self.cache_path = self.csv_path + CACHE_SUFFIX
        self.meta_path = self.csv_path + META_SUFFIX
        self.allow_extrapolation = allow_extrapolation
        self._ensure_cache()
        self.x, self.y = _load_cache(self.cache_path)
        self.x_min = float(self.x[0])
        self.x_max = float(self.x[-1])

    def _ensure_cache(self) -> None:
        size, mtime_ns = _file_sig(self.csv_path)
        needs_rebuild = True
        if os.path.exists(self.cache_path) and os.path.exists(self.meta_path):
            try:
                meta = _read_meta(self.meta_path)
                if (meta.source_path == self.csv_path and meta.source_size == size and meta.source_mtime_ns == mtime_ns and os.path.exists(self.cache_path)):
                    needs_rebuild = False
            except Exception:
                needs_rebuild = True
        if needs_rebuild:
            x, y = _clean_xy_from_csv(self.csv_path)
            if len(x) < 2:
                raise ValueError('Not enough data points to build interpolator (need >= 2).')
            _save_cache(self.cache_path, x, y)
            meta = CacheMeta(source_path=self.csv_path, source_size=size, source_mtime_ns=mtime_ns, x_min=float(x[0]), x_max=float(x[-1]), n=int(len(x)))
            _write_meta(self.meta_path, meta)

    def _interp_linear(self, t):
        import numpy as _np
        x = self.x; y = self.y
        t = _np.asarray(t, dtype=float)
        idx = _np.searchsorted(x, t, side='left')
        left_of_first = idx == 0
        right_of_last = idx == len(x)
        idx = _np.clip(idx, 1, len(x)-1)
        x0 = x[idx - 1]; x1 = x[idx]
        y0 = y[idx - 1]; y1 = y[idx]
        denom = (x1 - x0)
        denom[denom == 0.0] = 1.0
        w = (t - x0) / denom
        yi = y0 * (1.0 - w) + y1 * w
        if not self.allow_extrapolation:
            yi[left_of_first] = y[0]
            yi[right_of_last] = y[-1]
        else:
            if _np.any(left_of_first):
                xi0, xi1 = x[0], x[1]
                yi0, yi1 = y[0], y[1]
                m = (yi1 - yi0) / (xi1 - xi0)
                yi[left_of_first] = yi0 + m * (t[left_of_first] - xi0)
            if _np.any(right_of_last):
                xi0, xi1 = x[-2], x[-1]
                yi0, yi1 = y[-2], y[-1]
                m = (yi1 - yi0) / (xi1 - xi0)
                yi[right_of_last] = yi1 + m * (t[right_of_last] - xi1)
        return yi

    def __call__(self, t: Union[float, Iterable, 'np.ndarray']):
        import numpy as _np
        arr = _np.atleast_1d(_np.array(t, dtype=float))
        yi = self._interp_linear(arr)
        return float(yi[0]) if _np.isscalar(t) else yi
