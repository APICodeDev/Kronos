// Apply the saved preference before styles load to avoid a light flash.
try {
    const theme = localStorage.getItem('kronos-theme');
    document.documentElement.dataset.bsTheme = theme === 'light' ? 'light' : 'dark';
} catch (_) {
    document.documentElement.dataset.bsTheme = 'dark';
}
