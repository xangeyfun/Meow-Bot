document.addEventListener("DOMContentLoaded", () => {
  const root = document.documentElement;
  const themeToggle = document.querySelector("[data-theme-toggle]");
  const themeMeta = document.querySelector('meta[name="theme-color"]');
  const meowButton = document.querySelector("[data-meow]");
  const meowOutput = document.querySelector("[data-meow-output]");
  const meowArt = document.querySelector("[data-meow-art]");
  const copyButtons = document.querySelectorAll("[data-copy]");
  const statNodes = document.querySelectorAll("[data-stat]");

  const refreshStats = async () => {
    if (!statNodes.length) {
      return;
    }
    try {
      const response = await fetch("/api/stats", {
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      statNodes.forEach((node) => {
        const key = node.getAttribute("data-stat");
        if (typeof data[key] === "number") {
          node.textContent = data[key].toLocaleString("en-US");
        }
      });
    } catch (error) {
      /* live stats are optional */
    }
  };

  if (statNodes.length) {
    refreshStats();
    window.setInterval(() => {
      if (document.visibilityState === "visible") {
        refreshStats();
      }
    }, 15000);
  }

  const syncTheme = () => {
    const dark = root.getAttribute("data-theme") === "dark";
    const label = dark ? "switch to light mode" : "switch to dark mode";
    if (themeToggle) {
      themeToggle.setAttribute("aria-label", label);
      themeToggle.setAttribute("title", label);
    }
    if (themeMeta) {
      themeMeta.setAttribute("content", dark ? "#15120e" : "#E85D2A");
    }
  };

  if (themeToggle) {
    syncTheme();
    themeToggle.addEventListener("click", () => {
      const next =
        root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try {
        window.localStorage.setItem("meow-theme", next);
      } catch (error) {
        /* storage is optional */
      }
      syncTheme();
    });
  }

  const meows = [
    "meow.",
    "mrrp.",
    "mew!",
    "mrow.",
    "nya~",
    "purr.",
    "mreow?",
    "meow meow.",
    "mrrrow.",
    "mew mew.",
  ];

  const sayMeow = () => {
    if (!meowOutput) {
      return;
    }
    let next = meowOutput.textContent;
    while (next === meowOutput.textContent) {
      next = meows[Math.floor(Math.random() * meows.length)];
    }
    meowOutput.textContent = next;
    meowOutput.classList.remove("pop");
    void meowOutput.offsetWidth;
    meowOutput.classList.add("pop");
    if (meowArt) {
      meowArt.classList.remove("wiggle");
      void meowArt.offsetWidth;
      meowArt.classList.add("wiggle");
    }
  };

  if (meowButton) {
    meowButton.addEventListener("click", sayMeow);
  }
  if (meowArt) {
    meowArt.addEventListener("click", sayMeow);
    meowArt.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        sayMeow();
      }
    });
  }

  copyButtons.forEach((button) => {
    button.addEventListener("click", async () => {
      const value = button.getAttribute("data-copy");
      if (!value) {
        return;
      }

      try {
        await navigator.clipboard.writeText(value);
        const original = button.textContent;
        button.textContent = "copied";
        window.setTimeout(() => {
          button.textContent = original;
        }, 1200);
      } catch (error) {
        return;
      }
    });
  });
});
