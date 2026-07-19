// AI Tools Pricing - Main JS
(function () {
  'use strict';

  // Mobile menu toggle
  const menuToggle = document.getElementById('menu-toggle');
  const mainNav = document.getElementById('main-nav');
  if (menuToggle && mainNav) {
    menuToggle.addEventListener('click', function () {
      mainNav.classList.toggle('open');
      const expanded = mainNav.classList.contains('open');
      menuToggle.setAttribute('aria-expanded', expanded);
    });
  }

  // Language switcher dropdown
  document.querySelectorAll('.lang-switcher').forEach(function (switcher) {
    const btn = switcher.querySelector('.lang-btn');
    const dropdown = switcher.querySelector('.lang-dropdown');
    if (!btn || !dropdown) return;

    btn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      dropdown.classList.toggle('open');
      const expanded = dropdown.classList.contains('open');
      btn.setAttribute('aria-expanded', expanded);
    });

    document.addEventListener('click', function () {
      dropdown.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    });
  });

  // Header search form submit
  document.querySelectorAll('.header-search form, .hero-search form').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      const input = form.querySelector('input[type="search"], input[type="text"]');
      if (!input || !input.value.trim()) return;
      const lang = document.documentElement.lang || 'en';
      const langPrefix = lang === 'en-us' || lang === 'en' ? '' : '/' + lang.split('-')[0] + '/';
      window.location.href = window.location.origin + langPrefix + 'search/?q=' + encodeURIComponent(input.value.trim());
    });
  });

  // Lazy load images fallback
  if (!('loading' in HTMLImageElement.prototype)) {
    document.querySelectorAll('img[loading="lazy"]').forEach(function (img) {
      img.src = img.dataset.src || img.src;
    });
  }

  // Add active class to current nav link
  const currentPath = window.location.pathname;
  document.querySelectorAll('.main-nav a').forEach(function (link) {
    const href = link.getAttribute('href');
    if (!href) return;
    if (currentPath === href || (href !== '/' && currentPath.startsWith(href))) {
      link.classList.add('active');
    }
  });

  // Smooth scroll for anchor links
  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
    anchor.addEventListener('click', function (e) {
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
})();
