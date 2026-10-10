(function() {
    'use strict';
    const el = id => document.getElementById(id);
    function chartTheme(layout = {}) {
        const dark = document.documentElement.dataset.bsTheme !== 'light';
        const surface = dark ? '#151d2a' : '#ffffff';
        const text = dark ? '#e4eaf3' : '#243247';
        const grid = dark ? '#2b384b' : '#e4e9f1';
        return {...layout, template: {}, autosize: true, height: el('chart').clientHeight || 600,
            paper_bgcolor: surface, plot_bgcolor: surface,
            font: {...layout.font, color: text, family: 'system-ui, sans-serif'},
            margin: {l: 30, r: 90, t: 70, b: 60},
            legend: {...layout.legend, orientation: 'h', y: 1.12, x: 0, font: {color: text}, bgcolor: surface},
            xaxis: {...layout.xaxis, gridcolor: grid, linecolor: grid, zerolinecolor: grid, tickfont: {color: text}, automargin: true},
            yaxis: {...layout.yaxis, side: 'right', gridcolor: grid, linecolor: grid, zerolinecolor: grid, tickfont: {color: text}, automargin: true}
        };
    }
    function resizeChart() {
        const chart = el('chart');
        if (el('results-panel').hidden || !chart.data || typeof Plotly === 'undefined') return;
        Plotly.relayout(chart, {height: chart.clientHeight || 600, autosize: true});
        Plotly.Plots.resize(chart);
    }
    function showTab(name, focus = false) {
        for (const key of ['config', 'results']) {
            const selected = key === name;
            el(key + '-panel').hidden = !selected;
            const tab = el(key + '-tab');
            tab.classList.toggle('active', selected);
            tab.setAttribute('aria-selected', String(selected));
            tab.tabIndex = selected ? 0 : -1;
        }
        if (focus) el(name + '-tab').focus();
        if (name === 'results') requestAnimationFrame(resizeChart);
    }
    function setTheme(theme) {
        theme = theme === 'light' ? 'light' : 'dark';
        document.documentElement.dataset.bsTheme = theme;
        el('theme-select').value = theme;
        try { localStorage.setItem('kronos-theme', theme); } catch (_) { /* Storage may be unavailable. */ }
        const chart = el('chart');
        if (chart.data && typeof Plotly !== 'undefined') Plotly.relayout(chart, chartTheme(chart.layout));
    }
    function init() {
        el('theme-select').value = document.documentElement.dataset.bsTheme === 'light' ? 'light' : 'dark';
        el('theme-select').addEventListener('change', event => setTheme(event.target.value));
        for (const name of ['config', 'results']) {
            const tab = el(name + '-tab');
            tab.addEventListener('click', () => showTab(name));
            tab.addEventListener('keydown', event => {
                if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
                event.preventDefault();
                const next = event.key === 'Home' ? 'config' : event.key === 'End' ? 'results' : name === 'config' ? 'results' : 'config';
                showTab(next, true);
            });
        }
        el('back-to-config').addEventListener('click', () => showTab('config', true));
        let resizeTimer;
        window.addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(resizeChart, 150); });
    }
    function showResults(mode) {
        el('results-caption').hidden = false;
        el('results-empty').hidden = true;
        el('chart').hidden = false;
        el('results-badge').hidden = false;
        el('results-heading').textContent = mode === 'backtest' ? 'Comparación histórica' : `Últimas ${el('lookback').value} velas y predicción futura`;
        showTab('results', true);
    }
    function clearResults() {
        el('results-caption').hidden = true;
        if (typeof Plotly !== 'undefined') Plotly.purge('chart');
        el('chart').hidden = true;
        el('results-empty').hidden = false;
        el('results-badge').hidden = true;
        el('results-market-info').hidden = true;
    }
    window.Workspace = {init, showTab, showResults, clearResults, chartTheme, setTheme};
})();
