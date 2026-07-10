// Nitro Forge site interactions. Vanilla, dependency-free, progressive
// enhancement: all content is readable without JS; this only adds motion.
(() => {
  "use strict";
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Frame-sync helper: coalesces high-rate events (1000 Hz mice fire
  // pointermove far faster than the display refreshes) into at most one
  // style write per animation frame. This is the core anti-lag fix.
  const rafThrottle = (fn) => {
    let scheduled = false;
    let lastArgs;
    return (...args) => {
      lastArgs = args;
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(() => {
        scheduled = false;
        fn(...lastArgs);
      });
    };
  };

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

  // ---- download feedback toast --------------------------------------
  // The installer is served straight from this site (downloads/...exe with
  // the `download` attribute), so the click already "just downloads" - this
  // adds the "your download has started" confirmation users expect.
  document.querySelectorAll('a[href$="NitroForgeSetup.exe"]').forEach((a) => {
    a.addEventListener("click", () => {
      let toast = document.getElementById("dl-toast");
      if (!toast) {
        toast = document.createElement("div");
        toast.id = "dl-toast";
        toast.innerHTML =
          '<span class="dl-check"></span><div><b>Download started</b>' +
          "<small>Run NitroForgeSetup.exe when it finishes. Windows " +
          "SmartScreen may ask once - choose More info &gt; Run anyway.</small></div>";
        document.body.appendChild(toast);
      }
      toast.classList.remove("show");
      void toast.offsetWidth; // restart the animation
      toast.classList.add("show");
      clearTimeout(toast._t);
      toast._t = setTimeout(() => toast.classList.remove("show"), 7000);
    });
  });

  // ---- nav shadow + scroll progress --------------------------------
  const nav = document.getElementById("nav");
  const bar = document.querySelector(".scroll-progress");
  const onScroll = rafThrottle(() => {
    const y = window.scrollY;
    nav?.classList.toggle("scrolled", y > 12);
    if (bar) {
      const h = document.documentElement.scrollHeight - window.innerHeight;
      bar.style.transform = `scaleX(${h > 0 ? y / h : 0})`;
    }
  });
  if (bar) {
    bar.style.width = "100%";          // animate transform, not width
    bar.style.transformOrigin = "left";
    bar.style.transform = "scaleX(0)";
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  if (reduce) return; // skip pointer-driven motion for reduced-motion users

  // ---- magnetic buttons (frame-synced) ------------------------------
  document.querySelectorAll(".magnetic").forEach((el) => {
    const move = rafThrottle((e) => {
      const r = el.getBoundingClientRect();
      const mx = e.clientX - r.left - r.width / 2;
      const my = e.clientY - r.top - r.height / 2;
      el.style.transform = `translate(${mx * 0.18}px, ${my * 0.28}px)`;
    });
    el.addEventListener("pointermove", move, { passive: true });
    el.addEventListener("pointerleave", () => {
      // ease back with a temporary transition, then hand control to JS again
      el.style.transition = "transform .3s cubic-bezier(.22,1,.36,1)";
      el.style.transform = "";
      setTimeout(() => (el.style.transition = ""), 320);
    });
  });

  // ---- 3D tilt on cards / mock (frame-synced) ------------------------
  document.querySelectorAll("[data-tilt]").forEach((el) => {
    const move = rafThrottle((e) => {
      const r = el.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width - 0.5;
      const py = (e.clientY - r.top) / r.height - 0.5;
      el.style.transform = `perspective(900px) rotateY(${px * 6}deg) rotateX(${-py * 6}deg)`;
    });
    el.addEventListener("pointermove", move, { passive: true });
    el.addEventListener("pointerleave", () => {
      el.style.transition = "transform .35s cubic-bezier(.22,1,.36,1)";
      el.style.transform = "";
      setTimeout(() => (el.style.transition = ""), 370);
    });
  });

  // ---- background parallax: ONE composited transform on the wrapper,
  // not per-blob margin writes (margins force layout on every mousemove)
  const backdrop = document.querySelector(".backdrop");
  if (backdrop) {
    const drift = rafThrottle((e) => {
      const cx = e.clientX / window.innerWidth - 0.5;
      const cy = e.clientY / window.innerHeight - 0.5;
      backdrop.style.transform = `translate(${cx * 18}px, ${cy * 18}px) scale(1.03)`;
    });
    window.addEventListener("pointermove", drift, { passive: true });
  }
})();
