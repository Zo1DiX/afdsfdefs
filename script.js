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

  const sectionIds = ["home", "about", "timeline", "ideas", "test", "quiz", "legacy"];
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


  /* ------------------------------------------------------------------------
     Тест на время: 8 вопросов, 20 секунд на каждый
     ------------------------------------------------------------------------ */

  const quizApp = document.getElementById("quiz-app");

  if (quizApp && !quizApp.dataset.quizReady) {
    quizApp.dataset.quizReady = "true";

    const QUESTIONS = [
      {
        q: "Где Тьюринг работал во время Второй мировой войны?",
        options: ["Блетчли-парк", "Пентагон", "Массачусетский технологический институт", "ЦЕРН в Женеве"],
        answer: 0,
        explain: "1939–1945: Hut 8 в Блетчли-парке, взлом немецкой Enigma и работа над дешифратором «Бомба»."
      },
      {
        q: "В каком году Тьюринг описал «универсальную машину»?",
        options: ["1928", "1936", "1945", "1950"],
        answer: 1,
        explain: "Статья «On Computable Numbers» (1936) — фундамент теоретической информатики и идея программируемого компьютера."
      },
      {
        q: "Что такое машина Тьюринга?",
        options: ["Первый серийный компьютер", "Немецкая шифровальная машина", "Абстрактное устройство, способное выполнить любой алгоритм", "Прибор для взлома морских шифров"],
        answer: 2,
        explain: "Это мысленная модель: лента, головка и правила. Электронных компьютеров в 1936 году ещё не существовало."
      },
      {
        q: "Как называлась статья 1950 года о «думающих» машинах?",
        options: ["«On Computable Numbers»", "«Intelligent Machinery»", "«Химическая основа морфогенеза»", "«Computing Machinery and Intelligence»"],
        answer: 3,
        explain: "Именно в ней Тьюринг предложил игру в имитацию — то, что сегодня называют тестом Тьюринга."
      },
      {
        q: "В чём суть теста Тьюринга?",
        options: ["Машина собирает пазл быстрее человека", "Судья общается текстом с человеком и машиной и пытается понять, кто есть кто", "Робот повторяет мимику собеседника", "Машина сдаёт школьный экзамен"],
        answer: 1,
        explain: "Судить машину предлагается по её ответам — по наблюдаемому поведению, а не по внутреннему устройству."
      },
      {
        q: "Что Тьюринг описал в отчёте «Intelligent Machinery» (1948)?",
        options: ["Устройство интернета", "Первый язык программирования", "«Неорганизованные машины» — прообраз нейросетей", "Принцип работы банкноты"],
        answer: 2,
        explain: "Сети простых элементов, которые меняются и обучаются, — ранняя идея нейросетей и машинного обучения."
      },
      {
        q: "Какую проблему Тьюринг моделировал в работе 1952 года?",
        options: ["Полёты в космос", "Узоры природы — морфогенез", "Погоду в Лондоне", "Курс фунта стерлингов"],
        answer: 1,
        explain: "«Химическая основа морфогенеза»: как из реакции и диффузии рождаются пятна, полосы и другие узоры живой природы."
      },
      {
        q: "Какая награда в информатике носит имя Тьюринга?",
        options: ["Нобелевская премия", "Пулитцеровская премия", "Оскар", "Премия Тьюринга, учреждённая в 1966 году"],
        answer: 3,
        explain: "Премия Тьюринга появилась в 1966 году — её называют «Нобелевской премией» для информатиков."
      }
    ];

    const QUESTION_TIME = 20;
    const QUESTION_MS = QUESTION_TIME * 1000;
    const LETTERS = ["А", "Б", "В", "Г"];
    const BEST_KEY = "turing-quiz-best";
    const TICK = 100;

    let timerId = null;
    let state = null;
    let best = -1;

    try {
      const saved = Number(window.localStorage.getItem(BEST_KEY));
      if (Number.isFinite(saved) && saved > 0) best = saved;
    } catch (error) {
      best = -1;
    }

    const rankFor = (score) => {
      if (score >= 8) {
        return {
          title: "Машина думает",
          text: "Идеальный результат. Тьюринг назначил бы вас судьёй высшей категории."
        };
      }
      if (score >= 6) {
        return {
          title: "Главный криптоаналитик",
          text: "Блетчли-парк был бы рад видеть вас в Hut 8. До идеала — один шаг."
        };
      }
      if (score >= 4) {
        return {
          title: "Студент Кингс-колледжа",
          text: "Крепкая база. Перечитайте разделы «Хронология» и «Идеи» — и попробуйте снова."
        };
      }
      return {
        title: "Судья в замешательстве",
        text: "В этот раз машина вас обманула. Ответы на все вопросы спрятаны на странице — вернитесь к истории."
      };
    };

    const stopTimer = () => {
      if (timerId !== null) {
        window.clearInterval(timerId);
        timerId = null;
      }
    };

    const updateTimerUI = () => {
      if (!state) return;
      const timeEl = quizApp.querySelector("#quiz-time");
      const fillEl = quizApp.querySelector("#quiz-fill");
      if (!timeEl || !fillEl) return;
      timeEl.textContent = String(Math.ceil(state.remainingMs / 1000));
      fillEl.style.width = `${Math.max(0, (state.remainingMs / QUESTION_MS) * 100)}%`;
      const box = fillEl.closest(".quiz__timer");
      if (box) {
        box.classList.toggle("is-warn", state.remainingMs <= 10000 && state.remainingMs > 5000);
        box.classList.toggle("is-danger", state.remainingMs <= 5000);
      }
    };

    const startTimer = () => {
      stopTimer();
      timerId = window.setInterval(() => {
        if (!state) {
          stopTimer();
          return;
        }
        state.remainingMs -= TICK;
        if (state.remainingMs <= 0) {
          state.remainingMs = 0;
          updateTimerUI();
          stopTimer();
          timeOut();
          return;
        }
        updateTimerUI();
      }, TICK);
    };

    const showExplain = (correctIndex, pickedIndex) => {
      const item = QUESTIONS[state.index];
      const explainEl = quizApp.querySelector("#quiz-explain");
      const labelEl = quizApp.querySelector("#quiz-explain-label");
      const textEl = quizApp.querySelector("#quiz-explain-text");
      if (!explainEl || !labelEl || !textEl) return;

      quizApp.querySelectorAll(".quiz__option").forEach((button, i) => {
        button.disabled = true;
        if (i === correctIndex) button.classList.add("is-correct");
        if (i === pickedIndex && pickedIndex !== correctIndex) button.classList.add("is-wrong");
      });

      if (pickedIndex === correctIndex) {
        state.score += 1;
        state.results.push("correct");
        labelEl.textContent = "Верно";
      } else if (pickedIndex === -1) {
        state.results.push("timeout");
        labelEl.textContent = "Время вышло";
      } else {
        state.results.push("wrong");
        labelEl.textContent = "Мимо";
      }

      const scoreEl = quizApp.querySelector(".quiz__score");
      if (scoreEl) scoreEl.textContent = `СЧЁТ: ${state.score}`;
      textEl.textContent = item.explain;
      explainEl.hidden = false;
      explainEl.querySelector("#quiz-next")?.focus({ preventScroll: true });
    };

    const chooseAnswer = (index) => {
      if (!state || state.locked) return;
      state.locked = true;
      stopTimer();
      showExplain(QUESTIONS[state.index].answer, index);
    };

    const timeOut = () => {
      if (!state || state.locked) return;
      state.locked = true;
      showExplain(QUESTIONS[state.index].answer, -1);
    };

    const renderQuestion = () => {
      const item = QUESTIONS[state.index];
      const isLast = state.index === QUESTIONS.length - 1;
      quizApp.innerHTML = `
        <div class="quiz__screen">
          <div class="quiz__status">
            <span class="quiz__counter">ВОПРОС ${state.index + 1} / ${QUESTIONS.length}</span>
            <span class="quiz__score">СЧЁТ: ${state.score}</span>
          </div>
          <div class="quiz__timer" aria-hidden="true">
            <span class="quiz__timer-num" id="quiz-time">${QUESTION_TIME}</span>
            <span class="quiz__timer-track"><span class="quiz__timer-fill" id="quiz-fill"></span></span>
          </div>
          <p class="quiz__question">${item.q}</p>
          <div class="quiz__options" role="group" aria-label="Варианты ответа">
            ${item.options
              .map(
                (option, i) => `
              <button class="quiz__option" type="button" data-index="${i}">
                <span class="quiz__option-letter" aria-hidden="true">${LETTERS[i]}</span>
                <span>${option}</span>
              </button>`
              )
              .join("")}
          </div>
          <div class="quiz__explain" id="quiz-explain" hidden>
            <p class="quiz__explain-label" id="quiz-explain-label"></p>
            <p class="quiz__explain-text" id="quiz-explain-text"></p>
            <button class="button button--primary quiz__next" type="button" id="quiz-next">
              ${isLast ? "К результату" : "Следующий вопрос"}
              <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
            </button>
          </div>
        </div>`;

      quizApp.querySelectorAll(".quiz__option").forEach((button) => {
        button.addEventListener("click", () => chooseAnswer(Number(button.dataset.index)));
      });
      quizApp.querySelector("#quiz-next")?.addEventListener("click", nextQuestion);

      state.remainingMs = QUESTION_MS;
      state.locked = false;
      updateTimerUI();
      startTimer();
    };

    const nextQuestion = () => {
      if (!state) return;
      if (state.index === QUESTIONS.length - 1) {
        renderResult();
        return;
      }
      state.index += 1;
      renderQuestion();
    };

    const commitBest = (score) => {
      const isRecord = score > best && score > 0;
      if (isRecord) {
        best = score;
        try {
          window.localStorage.setItem(BEST_KEY, String(best));
        } catch (error) {
          /* localStorage может быть недоступен */
        }
      }
      return isRecord;
    };

    const renderResult = () => {
      stopTimer();
      const isRecord = commitBest(state.score);
      const rank = rankFor(state.score);
      const dots = state.results
        .map((result) => `<span class="quiz__dot quiz__dot--${result}"></span>`)
        .join("");
      quizApp.innerHTML = `
        <div class="quiz__result">
          <p class="quiz__label">РЕЗУЛЬТАТ</p>
          <p class="quiz__total"><strong>${state.score}</strong><span>/ ${QUESTIONS.length}</span></p>
          <div class="quiz__dots" role="list" aria-label="Ответы по вопросам">${dots}</div>
          <p class="quiz__rank">${rank.title}</p>
          <p class="quiz__rank-text">${rank.text}</p>
          ${isRecord ? '<p class="quiz__record">Новый рекорд — сохранён на этой странице</p>' : ""}
          <div class="quiz__result-actions">
            <button class="button button--primary" type="button" id="quiz-restart">
              Пройти ещё раз
              <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 12a8 8 0 1 1-2.34-5.66M20 4v5h-5"/></svg>
            </button>
            <a class="button button--ghost" href="#about">Перечитать историю</a>
          </div>
        </div>`;
      quizApp.querySelector("#quiz-restart")?.addEventListener("click", startQuiz);
    };

    const renderStart = () => {
      stopTimer();
      state = null;
      const bestLine =
        best >= 0
          ? `<p class="quiz__best">Лучший результат: <strong>${best} / ${QUESTIONS.length}</strong></p>`
          : "";
      quizApp.innerHTML = `
        <div class="quiz__start">
          <p class="quiz__label">ТЕСТ ПО ТЕМЕ</p>
          <p class="quiz__lead">Восемь вопросов по материалам страницы: биография, Enigma, машина Тьюринга, игра в имитацию и наследие.</p>
          <ul class="quiz__rules">
            <li><span>8</span>вопросов по теме</li>
            <li><span>20</span>секунд на каждый</li>
            <li><span>✓</span>пояснение после каждого ответа</li>
          </ul>
          ${bestLine}
          <button class="button button--primary quiz__start-btn" type="button" id="quiz-start">
            Начать тест
            <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
          </button>
        </div>`;
      quizApp.querySelector("#quiz-start")?.addEventListener("click", startQuiz);
    };

    const startQuiz = () => {
      state = { index: 0, score: 0, results: [], remainingMs: QUESTION_MS, locked: false };
      renderQuestion();
    };

    renderStart();
  }
})();

