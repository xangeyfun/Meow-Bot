document.addEventListener("DOMContentLoaded", () => {
  const copyButtons = document.querySelectorAll("[data-copy]");

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
