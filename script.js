/* ==========================================================================
   TURING — interactions
   ========================================================================== */

(() => {
  "use strict";

  const root = document.documentElement;
  const body = document.body;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const finePointer = window.matchMedia("(pointer: fine)");
  const isDesktop = () => window.innerWidth > 1000;

  /* ------------------------------------------------------------------------
     Mobile navigation
     ------------------------------------------------------------------------ */

  const menuToggle = document.getElementById("menu-toggle");
  const mainNav = document.getElementById("main-nav");
  const navLinks = [...document.querySelectorAll(".main-nav__link")];

  const setMenu = (open) => {
    if (!menuToggle || !mainNav) return;
    menuToggle.setAttribute("aria-expanded", String(open));
    menuToggle.setAttribute("aria-label", open ? "Закрыть меню" : "Открыть меню");
    mainNav.classList.toggle("is-open", open);
    body.classList.toggle("is-menu-open", open);

    if (open) {
      window.requestAnimationFrame(() => {
        navLinks[0]?.focus({ preventScroll: true });
      });
    } else if (!isDesktop() && mainNav.contains(document.activeElement)) {
      menuToggle.focus({ preventScroll: true });
    }
  };

  menuToggle?.addEventListener("click", () => {
    setMenu(menuToggle.getAttribute("aria-expanded") !== "true");
  });

  navLinks.forEach((link) => {
    link.addEventListener("click", () => setMenu(false));
  });

  document.addEventListener("click", (event) => {
    if (!mainNav?.classList.contains("is-open")) return;
    if (mainNav.contains(event.target) || menuToggle?.contains(event.target)) return;
    setMenu(false);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !mainNav?.classList.contains("is-open")) return;
    setMenu(false);
    menuToggle?.focus({ preventScroll: true });
  });

  window.addEventListener("resize", () => {
    if (isDesktop()) setMenu(false);
  });

  /* ------------------------------------------------------------------------
     Active navigation item
     ------------------------------------------------------------------------ */

  const sectionIds = ["home", "about", "timeline", "ideas", "legacy"];
  const navBySection = new Map(
    navLinks.map((link) => [link.getAttribute("href")?.replace("#", ""), link])
  );
  let navTick = false;

  const updateActiveNav = () => {
    navTick = false;
    const marker = window.scrollY + window.innerHeight * 0.34;
    let current = sectionIds[0];

    sectionIds.forEach((id) => {
      const section = document.getElementById(id);
      if (!section) return;
      const top = section.getBoundingClientRect().top + window.scrollY;
      if (top <= marker) current = id;
    });

    navLinks.forEach((link) => {
      const active = link === navBySection.get(current);
      link.classList.toggle("is-active", active);
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  };

  const queueNavUpdate = () => {
    if (navTick) return;
    navTick = true;
    window.requestAnimationFrame(updateActiveNav);
  };

  window.addEventListener("scroll", queueNavUpdate, { passive: true });
  window.addEventListener("resize", queueNavUpdate);
  updateActiveNav();

  /* ------------------------------------------------------------------------
     Scroll reveal
     ------------------------------------------------------------------------ */

  const revealItems = [...document.querySelectorAll(".reveal")];

  revealItems.forEach((item) => {
    const delay = Number(item.dataset.delay || 0);
    if (delay) item.style.setProperty("--reveal-delay", `${delay}ms`);
  });

  if (reduceMotion.matches || !("IntersectionObserver" in window)) {
    revealItems.forEach((item) => item.classList.add("is-visible"));
  } else {
    const revealObserver = new IntersectionObserver(
      (entries, observer) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -7% 0px", threshold: 0.1 }
    );

    revealItems.forEach((item) => revealObserver.observe(item));
  }

  /* ------------------------------------------------------------------------
     Motion toggle
     ------------------------------------------------------------------------ */

  const motionToggle = document.getElementById("motion-toggle");
  let paused = false;

  const syncMotionState = () => {
    body.classList.toggle("is-paused", paused);
    if (!motionToggle) return;
    motionToggle.setAttribute("aria-pressed", String(paused));
    motionToggle.setAttribute(
      "aria-label",
      paused ? "Возобновить анимацию" : "Приостановить анимацию"
    );
  };

  motionToggle?.addEventListener("click", () => {
    paused = !paused;
    syncMotionState();
    if (paused) {
      stopParticles();
    } else {
      startParticles();
    }
  });

  /* ------------------------------------------------------------------------
     Canvas particle field
     ------------------------------------------------------------------------ */

  const canvas = document.getElementById("particle-canvas");
  const context = canvas?.getContext("2d");
  const hero = document.querySelector(".hero");
  let particles = [];
  let particleFrame = null;
  let canvasWidth = 0;
  let canvasHeight = 0;
  let dpr = 1;

  const particleCount = () => {
    if (!canvasWidth) return 0;
    return Math.max(24, Math.min(82, Math.round(canvasWidth / 17)));
  };

  const makeParticle = (width, height) => {
    const depth = Math.random();
    return {
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.16,
      vy: -0.05 - Math.random() * 0.16,
      r: 0.35 + depth * 1.35,
      alpha: 0.13 + depth * 0.5,
      pulse: Math.random() * Math.PI * 2,
      pulseSpeed: 0.004 + Math.random() * 0.012
    };
  };

  const seedParticles = () => {
    particles = Array.from({ length: particleCount() }, () =>
      makeParticle(canvasWidth, canvasHeight)
    );
  };

  const resizeCanvas = () => {
    if (!canvas || !context) return;
    const rect = canvas.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvasWidth = Math.max(1, rect.width);
    canvasHeight = Math.max(1, rect.height);
    canvas.width = Math.round(canvasWidth * dpr);
    canvas.height = Math.round(canvasHeight * dpr);
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    seedParticles();
    drawParticles();
  };

  const drawParticles = () => {
    if (!context) return;

    context.clearRect(0, 0, canvasWidth, canvasHeight);
    context.globalCompositeOperation = "lighter";

    for (let i = 0; i < particles.length; i += 1) {
      const particle = particles[i];
      const distance = Math.hypot(particle.x - canvasWidth / 2, particle.y - canvasHeight * 0.48);

      // Keep the center of the composition slightly cleaner.
      const centerFade = Math.min(1, Math.max(0.18, distance / (canvasWidth * 0.28)));
      const alpha = particle.alpha * centerFade;

      context.beginPath();
      context.arc(particle.x, particle.y, particle.r, 0, Math.PI * 2);
      context.fillStyle = `rgba(255, 74, 86, ${alpha})`;
      context.fill();

      if (particle.r > 1.1) {
        context.beginPath();
        context.arc(particle.x, particle.y, particle.r * 3.2, 0, Math.PI * 2);
        context.fillStyle = `rgba(255, 32, 54, ${alpha * 0.06})`;
        context.fill();
      }

      for (let j = i + 1; j < particles.length; j += 1) {
        const other = particles[j];
        const dx = particle.x - other.x;
        const dy = particle.y - other.y;
        const gap = Math.hypot(dx, dy);
        if (gap > 96) continue;
        context.beginPath();
        context.moveTo(particle.x, particle.y);
        context.lineTo(other.x, other.y);
        context.strokeStyle = `rgba(255, 70, 82, ${0.045 * (1 - gap / 96)})`;
        context.lineWidth = 0.6;
        context.stroke();
      }
    }

    context.globalCompositeOperation = "source-over";
  };

  const animateParticles = () => {
    if (!context || paused || document.hidden) {
      particleFrame = null;
      return;
    }

    particles.forEach((particle) => {
      particle.x += particle.vx;
      particle.y += particle.vy;
      particle.pulse += particle.pulseSpeed;

      if (particle.y < -10) {
        particle.y = canvasHeight + 10;
        particle.x = Math.random() * canvasWidth;
      }
      if (particle.x < -10) particle.x = canvasWidth + 10;
      if (particle.x > canvasWidth + 10) particle.x = -10;

      const shimmer = 0.82 + Math.sin(particle.pulse) * 0.18;
      particle.alpha = Math.min(0.72, Math.max(0.08, particle.alpha * 0.998 + 0.0004)) * shimmer;
    });

    drawParticles();
    particleFrame = window.requestAnimationFrame(animateParticles);
  };

  const startParticles = () => {
    if (!canvas || !context || paused || reduceMotion.matches || document.hidden) return;
    if (particleFrame !== null) return;
    particleFrame = window.requestAnimationFrame(animateParticles);
  };

  const stopParticles = () => {
    if (particleFrame !== null) {
      window.cancelAnimationFrame(particleFrame);
      particleFrame = null;
    }
  };

  if (canvas && context) {
    resizeCanvas();
    if (!reduceMotion.matches) startParticles();

    let resizeFrame = null;
    window.addEventListener("resize", () => {
      if (resizeFrame) window.cancelAnimationFrame(resizeFrame);
      resizeFrame = window.requestAnimationFrame(() => {
        resizeFrame = null;
        resizeCanvas();
      });
    });

    const heroObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !reduceMotion.matches) startParticles();
          else stopParticles();
        });
      },
      { threshold: 0.02 }
    );
    heroObserver.observe(hero);

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) stopParticles();
      else startParticles();
    });
  }

  /* ------------------------------------------------------------------------
     Subtle pointer parallax
     ------------------------------------------------------------------------ */

  const core = document.getElementById("core");

  if (core && hero) {
    let parallaxFrame = null;
    let targetX = 0;
    let targetY = 0;
    let currentX = 0;
    let currentY = 0;
    let animating = false;

    const renderParallax = () => {
      currentX += (targetX - currentX) * 0.09;
      currentY += (targetY - currentY) * 0.09;
      core.style.transform = `translate(calc(-50% + ${currentX.toFixed(2)}px), calc(-50% + ${currentY.toFixed(2)}px))`;

      if (Math.abs(targetX - currentX) > 0.05 || Math.abs(targetY - currentY) > 0.05) {
        parallaxFrame = window.requestAnimationFrame(renderParallax);
      } else {
        animating = false;
        parallaxFrame = null;
      }
    };

    const runParallax = () => {
      if (animating) return;
      animating = true;
      parallaxFrame = window.requestAnimationFrame(renderParallax);
    };

    hero.addEventListener(
      "pointermove",
      (event) => {
        if (!finePointer.matches || !isDesktop() || reduceMotion.matches || paused) return;
        const rect = hero.getBoundingClientRect();
        targetX = ((event.clientX - rect.left) / rect.width - 0.5) * 20;
        targetY = ((event.clientY - rect.top) / rect.height - 0.5) * 15;
        runParallax();
      },
      { passive: true }
    );

    hero.addEventListener("pointerleave", () => {
      targetX = 0;
      targetY = 0;
      runParallax();
    });

    window.addEventListener("resize", () => {
      if (!isDesktop()) {
        targetX = 0;
        targetY = 0;
        core.style.transform = "";
        if (parallaxFrame) window.cancelAnimationFrame(parallaxFrame);
        parallaxFrame = null;
        animating = false;
      }
    });
  }

  /* ------------------------------------------------------------------------
     Turing test illustration
     ------------------------------------------------------------------------ */

  const demo = document.getElementById("turing-demo");
  const choicePanel = document.getElementById("terminal-choice");
  const resultPanel = document.getElementById("terminal-result");
  const resultTitle = document.getElementById("result-title");
  const resultText = document.getElementById("result-text");
  const resetButton = document.getElementById("demo-reset");
  const choiceButtons = [...document.querySelectorAll("[data-choice]")];

  const resultCopy = {
    A: {
      title: "Вы выбрали A",
      text:
        "В этой иллюстрации A — человек, B — машина. Но настоящий тест не даёт судье заглянуть внутрь: он видит только текст. Если бы B ответил чуть убедительнее, отличить его было бы невозможно — в этом и состоит идея Тьюринга."
    },
    B: {
      title: "Вы выбрали B",
      text:
        "В этой иллюстрации B — машина, A — человек. Но судья в тесте Тьюринга не знает ответа заранее. Он оценивает только поведение — и именно поэтому вопрос «может ли машина думать?» превращается в вопрос «можно ли отличить её от человека?»."
    }
  };

  const revealResult = (choice) => {
    if (!choicePanel || !resultPanel || !resultTitle || !resultText) return;

    const copy = resultCopy[choice];
    resultTitle.textContent = copy.title;
    resultText.textContent = copy.text;
    choicePanel.hidden = true;
    resultPanel.hidden = false;
    demo?.classList.add("is-revealed");
    resetButton?.focus({ preventScroll: true });
  };

  choiceButtons.forEach((button) => {
    button.addEventListener("click", () => {
      revealResult(button.dataset.choice);
    });
  });

  resetButton?.addEventListener("click", () => {
    if (!choicePanel || !resultPanel) return;
    resultPanel.hidden = true;
    choicePanel.hidden = false;
    demo?.classList.remove("is-revealed");
    choiceButtons[0]?.focus({ preventScroll: true });
  });

  /* ------------------------------------------------------------------------
     Small polish: disable smooth anchor jumps while menu is open
     ------------------------------------------------------------------------ */

  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", () => {
      const targetId = anchor.getAttribute("href");
      if (!targetId || targetId === "#") return;
      const target = document.querySelector(targetId);
      if (!target) return;

      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        target.scrollIntoView({ behavior: "auto", block: "start" });
      }
    });
  });
})();
