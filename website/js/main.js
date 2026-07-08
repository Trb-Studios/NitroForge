// Scroll-reveal animations (progressive enhancement - content is visible
// without JS because we only add the .reveal transforms when supported).
const io = new IntersectionObserver(
  (entries) => {
    for (const e of entries) {
      if (e.isIntersecting) {
        e.target.classList.add("in");
        io.unobserve(e.target);
      }
    }
  },
  { threshold: 0.12 },
);

document.querySelectorAll(".reveal").forEach((el) => io.observe(el));

// Elements already in the viewport on load reveal immediately.
requestAnimationFrame(() => {
  document.querySelectorAll(".reveal").forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.top < window.innerHeight * 0.9) el.classList.add("in");
  });
});
