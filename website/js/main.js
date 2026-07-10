// Nitro Forge site interactions. Vanilla, dependency-free, progressive
// enhancement: all content is readable without JS; this only adds motion.
(() => {
  "use strict";
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- split the hero headline into animated words ------------------
  document.querySelectorAll("[data-reveal-split]").forEach((el) => {
    const words = el.textContent.split(" ");
    el.textContent = "";
    words.forEach((w, i) => {
      const span = document.createElement("span");
      span.className = "word";
      span.textContent = w + (i < words.length - 1 ? " " : "");
      span.style.animationDelay = `${0.15 + i * 0.06}s`;
      el.appendChild(span);
    });
  });

  // ---- scroll-reveal engine ----------------------------------------
  const reveal = (el) => el.classList.add("in");
  if ("IntersectionObserver" in window && !reduce) {
    const io = new IntersectionObserver(
      (entries, obs) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            reveal(e.target);
            if (e.target.hasAttribute("data-count")) animateCount(e.target);
            if (e.target.querySelector) e.target.querySelectorAll?.("[data-v]").forEach(fillRing);
            obs.unobserve(e.target);
          }
        }
      },
      { threshold: 0.14, rootMargin: "0px 0px -8% 0px" },
    );
    document.querySelectorAll("[data-reveal], [data-count], .ring").forEach((el) => io.observe(el));
  } else {
    document.querySelectorAll("[data-reveal]").forEach(reveal);
    document.querySelectorAll("[data-count]").forEach((el) => (el.textContent = el.dataset.count + (el.dataset.suffix || "")));
    document.querySelectorAll(".ring").forEach((r) => (r.style.setProperty("--v", r.dataset.v), setRingText(r, r.dataset.raw || r.dataset.v)));
  }

  // ---- animated counters -------------------------------------------
  function animateCount(el) {
    const target = parseFloat(el.dataset.count);
    const suffix = el.dataset.suffix || "";
    const dur = 1400;
    const start = performance.now();
    const step = (now) => {
      const p = Math.min((now - start) / dur, 1);
      const eased = 1 - Math.pow(1 - p, 3); // easeOutCubic
      const val = Math.round(target * eased);
      el.textContent = val.toLocaleString() + suffix;
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  // ---- gauge ring fill + number ------------------------------------
  function setRingText(ring, val) {
    const b = ring.querySelector("b");
    if (b) b.textContent = val;
  }
  function fillRing(ring) {
    const target = parseFloat(ring.dataset.v);
    const raw = ring.dataset.raw ? parseFloat(ring.dataset.raw) : target;
    const dur = 1500;
    const start = performance.now();
    const step = (now) => {
      const p = Math.min((now - start) / dur, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      ring.style.setProperty("--v", (target * eased).toFixed(1));
      setRingText(ring, Math.round(raw * eased));
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  // ---- nav shadow + scroll progress --------------------------------
  const nav = document.getElementById("nav");
  const bar = document.querySelector(".scroll-progress");
  const onScroll = () => {
    const y = window.scrollY;
    nav?.classList.toggle("scrolled", y > 12);
    if (bar) {
      const h = document.documentElement.scrollHeight - window.innerHeight;
      bar.style.width = `${h > 0 ? (y / h) * 100 : 0}%`;
    }
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  if (reduce) return; // skip pointer-driven motion for reduced-motion users

  // ---- magnetic buttons --------------------------------------------
  document.querySelectorAll(".magnetic").forEach((el) => {
    el.addEventListener("pointermove", (e) => {
      const r = el.getBoundingClientRect();
      const mx = e.clientX - r.left - r.width / 2;
      const my = e.clientY - r.top - r.height / 2;
      el.style.transform = `translate(${mx * 0.18}px, ${my * 0.28}px)`;
    });
    el.addEventListener("pointerleave", () => (el.style.transform = ""));
  });

  // ---- 3D tilt on cards / mock -------------------------------------
  document.querySelectorAll("[data-tilt]").forEach((el) => {
    el.addEventListener("pointermove", (e) => {
      const r = el.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width - 0.5;
      const py = (e.clientY - r.top) / r.height - 0.5;
      el.style.transform = `perspective(900px) rotateY(${px * 6}deg) rotateX(${-py * 6}deg)`;
    });
    el.addEventListener("pointerleave", () => (el.style.transform = ""));
  });

  // ---- parallax the aurora blobs to the pointer --------------------
  const blobs = document.querySelectorAll(".aurora");
  window.addEventListener(
    "pointermove",
    (e) => {
      const cx = e.clientX / window.innerWidth - 0.5;
      const cy = e.clientY / window.innerHeight - 0.5;
      blobs.forEach((b, i) => {
        const depth = (i + 1) * 14;
        b.style.marginLeft = `${cx * depth}px`;
        b.style.marginTop = `${cy * depth}px`;
      });
    },
    { passive: true },
  );
})();
