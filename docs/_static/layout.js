document.addEventListener("DOMContentLoaded", () => {
  const page = document.querySelector(".page");
  const tocDrawer = document.querySelector("aside.toc-drawer");
  if (!page || !tocDrawer) {
    return;
  }
  if (tocDrawer.classList.contains("no-toc")) {
    page.classList.add("no-right-toc");
  }
});
