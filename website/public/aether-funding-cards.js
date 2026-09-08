/* SPDX-License-Identifier: MIT */
(() => {
  'use strict';
  document.documentElement.classList.add('js');

  const items = [...document.querySelectorAll('.reveal')];
  if (!('IntersectionObserver' in window) || matchMedia('(prefers-reduced-motion: reduce)').matches) {
    items.forEach(el => el.classList.add('in'));
    return;
  }
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('in');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -40px' });
  items.forEach((el, i) => {
    el.style.transitionDelay = `${Math.min((i % 3) * 70, 140)}ms`;
    observer.observe(el);
  });
})();
