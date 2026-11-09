(function () {
  var root = document.documentElement;
  var stored = null;

  try {
    stored = window.localStorage.getItem("meow-theme");
  } catch (error) {
    stored = null;
  }

  var systemDark =
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;
  var theme =
    stored === "light" || stored === "dark"
      ? stored
      : systemDark
        ? "dark"
        : "light";

  root.setAttribute("data-theme", theme);

  var meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    meta.setAttribute("content", theme === "dark" ? "#15120e" : "#E85D2A");
  }
})();
