'use strict';
{
    function setTheme(mode) {
        const selected = mode === 'dark' ? 'dark' : 'light';
        document.documentElement.dataset.theme = selected;
        localStorage.setItem('theme', selected);
    }

    function toggleTheme() {
        setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
    }

    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark' || savedTheme === 'light') {
        setTheme(savedTheme);
    } else {
        setTheme('light');
    }

    window.addEventListener('load', function () {
        Array.from(document.getElementsByClassName('theme-toggle')).forEach(function (button) {
            button.addEventListener('click', toggleTheme);
        });
    });
}
