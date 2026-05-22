// Expand the Blog section in the sidebar by default on every page load,
// including navigation.instant transitions.  Targets only the nav item
// whose submenu contains a link ending in "blog/" — not every section.
document$.subscribe(function () {
  document.querySelectorAll(".md-nav__item--nested").forEach(function (item) {
    if (!item.querySelector("a[href$='blog/']")) return;
    var toggle = item.querySelector("input.md-nav__toggle");
    if (toggle && !toggle.checked) toggle.checked = true;
  });
});
