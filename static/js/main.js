document.addEventListener("DOMContentLoaded", () => {
  const root = document.documentElement;
  const themeToggle = document.querySelector("[data-theme-toggle]");
  const themeMeta = document.querySelector('meta[name="theme-color"]');
  const meowButton = document.querySelector("[data-meow]");
  const meowOutput = document.querySelector("[data-meow-output]");
  const meowArt = document.querySelector("[data-meow-art]");
  const copyButtons = document.querySelectorAll("[data-copy]");
  const statNodes = document.querySelectorAll("[data-stat]");
  const trailLayer = document.querySelector("[data-cursor-trail]");

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer =
    window.matchMedia("(pointer: fine)").matches &&
    window.matchMedia("(hover: hover)").matches;

  const spawnBurst = (x, y) => {
    if (reducedMotion) {
      return;
    }
    const friend = document.createElement("span");
    friend.className = "float-friend";
    friend.textContent = "mrrp";
    friend.style.left = `${x}px`;
    friend.style.top = `${y}px`;
    friend.style.setProperty("--dx", `${(Math.random() * 32 - 16).toFixed(1)}px`);
    friend.style.setProperty("--rot", `${(Math.random() * 12 - 6).toFixed(1)}deg`);
    document.body.appendChild(friend);
    window.setTimeout(() => friend.remove(), 1150);
  };

  const syncTheme = () => {
    const dark = root.getAttribute("data-theme") === "dark";
    const label = dark ? "switch to light mode" : "switch to dark mode";
    if (themeToggle) {
      themeToggle.setAttribute("aria-label", label);
      themeToggle.setAttribute("title", label);
    }
    if (themeMeta) {
      themeMeta.setAttribute("content", dark ? "#17110c" : "#E8682F");
    }
  };

  if (themeToggle) {
    syncTheme();
    themeToggle.addEventListener("click", () => {
      const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try {
        window.localStorage.setItem("meow-theme", next);
      } catch (error) {
        /* storage is optional */
      }
      syncTheme();
      themeToggle.classList.remove("is-flipping");
      void themeToggle.offsetWidth;
      themeToggle.classList.add("is-flipping");
      window.setTimeout(() => themeToggle.classList.remove("is-flipping"), 460);
    });
  }

  const formatValue = (value) => {
    const rounded = Math.round(value * 10) / 10;
    if (Number.isInteger(rounded)) {
      return rounded.toLocaleString("en-US");
    }
    return rounded.toLocaleString("en-US", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    });
  };

  const bumpNumber = (node) => {
    const cell = node.parentElement;
    node.classList.remove("purr");
    if (cell) {
      cell.classList.remove("paw-pop");
    }
    void node.offsetWidth;
    node.classList.add("purr");
    if (cell) {
      cell.classList.add("paw-pop");
    }
    window.setTimeout(() => {
      node.classList.remove("purr");
      if (cell) {
        cell.classList.remove("paw-pop");
      }
    }, 780);
  };

  const animateNumber = (node, target, duration = 780) => {
    const from = Number(node.textContent.replace(/[^0-9.]/g, "")) || 0;
    if (reducedMotion || from === target) {
      node.textContent = formatValue(target);
      return;
    }

    const integerTarget = Number.isInteger(target);
    const started = performance.now();
    const step = (now) => {
      const progress = Math.min(1, (now - started) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      const value = from + (target - from) * eased;
      node.textContent = formatValue(integerTarget ? Math.round(value) : value);
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        node.textContent = formatValue(target);
        bumpNumber(node);
      }
    };
    requestAnimationFrame(step);
  };

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
          const firstPaint = node.getAttribute("data-counted") !== "1";
          if (firstPaint) {
            node.textContent = "0";
            node.setAttribute("data-counted", "1");
          }
          animateNumber(node, data[key], firstPaint ? 920 : 620);
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

  const wiggleArt = () => {
    if (!meowArt) {
      return;
    }
    meowArt.classList.remove("wiggle");
    void meowArt.offsetWidth;
    meowArt.classList.add("wiggle");
  };

  const sayMeow = (event) => {
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
    wiggleArt();

    const rect = meowArt ? meowArt.getBoundingClientRect() : null;
    const x = event && event.clientX ? event.clientX : rect ? rect.left + rect.width / 2 : window.innerWidth / 2;
    const y = event && event.clientY ? event.clientY : rect ? rect.top + rect.height / 2 : window.innerHeight / 2;
    spawnBurst(x, y);
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

  if (meowArt && !reducedMotion) {
    window.setInterval(() => {
      if (document.visibilityState === "visible" && Math.random() > 0.55) {
        wiggleArt();
      }
    }, 14000);
  }

  const addRipple = (button, event) => {
    if (reducedMotion) {
      return;
    }
    const rect = button.getBoundingClientRect();
    const ripple = document.createElement("span");
    ripple.className = "paw-ripple";
    ripple.style.left = `${event.clientX - rect.left}px`;
    ripple.style.top = `${event.clientY - rect.top}px`;
    button.appendChild(ripple);
    window.setTimeout(() => ripple.remove(), 620);
  };

  document.addEventListener("click", (event) => {
    const button = event.target.closest(".button, .nav-invite, .theme-toggle");
    if (!button || button.hasAttribute("data-meow")) {
      return;
    }
    if (button.classList.contains("button")) {
      addRipple(button, event);
    }
    spawnBurst(event.clientX, event.clientY);
  });

  copyButtons.forEach((button) => {
    button.addEventListener("click", async () => {
      const value = button.getAttribute("data-copy");
      if (!value) {
        return;
      }

      try {
        await navigator.clipboard.writeText(value);
        const original = button.textContent;
        button.textContent = "copied :3";
        button.classList.add("copied");
        window.setTimeout(() => {
          button.textContent = original;
          button.classList.remove("copied");
        }, 1400);
      } catch (error) {
        return;
      }
    });
  });

  const backToTop = document.querySelector("[data-back-to-top]");

  if (backToTop) {
    backToTop.addEventListener("click", () => {
      window.scrollTo({
        top: 0,
        behavior: reducedMotion ? "auto" : "smooth",
      });
    });
  }

  document.querySelectorAll(".docs-nav").forEach((nav) => {
    const active = nav.querySelector('[aria-current="page"]');
    if (!active || nav.scrollWidth <= nav.clientWidth) {
      return;
    }

    const navRect = nav.getBoundingClientRect();
    const activeRect = active.getBoundingClientRect();
    const target =
      nav.scrollLeft +
      activeRect.left -
      navRect.left -
      (navRect.width - activeRect.width) / 2;
    nav.scrollTo({ left: Math.max(0, target), behavior: "auto" });
  });

  const revealTargets = document.querySelectorAll(
    ".hero, .page-head, .section, .stat-grid, .card-grid, .card, .stat-card, .steps li, .status-panel, .table-wrap, .shot-card"
  );

  if (!reducedMotion && "IntersectionObserver" in window && revealTargets.length) {
    revealTargets.forEach((node, index) => {
      node.classList.add("reveal");
      node.style.setProperty("--reveal-delay", `${Math.min(index % 6, 5) * 55}ms`);
    });

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -36px 0px" }
    );

    revealTargets.forEach((node) => observer.observe(node));
  }

  if (trailLayer && finePointer && !reducedMotion) {
    let lastX = 0;
    let lastY = 0;
    let lastTime = 0;

    window.addEventListener(
      "pointermove",
      (event) => {
        if (event.pointerType && event.pointerType !== "mouse") {
          return;
        }
        const now = performance.now();
        if (now - lastTime < 45) {
          return;
        }
        const dx = event.clientX - lastX;
        const dy = event.clientY - lastY;
        if (dx * dx + dy * dy < 110) {
          return;
        }
        lastTime = now;
        lastX = event.clientX;
        lastY = event.clientY;

        const paw = document.createElement("span");
        paw.className = "trail-paw";
        paw.style.left = `${event.clientX}px`;
        paw.style.top = `${event.clientY}px`;
        paw.style.setProperty("--trail-rot", `${(Math.random() * 22 - 11).toFixed(1)}deg`);
        trailLayer.appendChild(paw);
        if (trailLayer.childElementCount > 24) {
          trailLayer.firstElementChild.remove();
        }
        window.setTimeout(() => paw.remove(), 820);
      },
      { passive: true }
    );
  }
});
