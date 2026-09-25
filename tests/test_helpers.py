from mediagrab.downloader import _safe_name


def test_safe_name_removes_windows_invalid_chars():
    assert _safe_name('a:b*c?d"e<f>g|h') == "a_b_c_d_e_f_g_h"
