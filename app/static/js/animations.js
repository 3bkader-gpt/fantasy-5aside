/**
 * Animation helpers for Fantasy 5-a-Side.
 * Uses native Web Animations API - no CDN, respects prefers-reduced-motion.
 */
(function () {
    "use strict";

    const prefersReducedMotion = () =>
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const animateEl = (el, keyframes, options = {}) => {
        if (!el || prefersReducedMotion()) return Promise.resolve();
        const duration = (options.duration ?? 0.3) * 1000;
        const easing = options.easing ?? "ease-out";
        const anim = el.animate(keyframes, {
            duration,
            easing,
            fill: "forwards",
        });
        return anim.finished;
    };

    window.FantasyMotion = {
        /** Nav sheet: slide up + fade in */
        navSheetOpen(sheetContent) {
            if (!sheetContent) return;
            sheetContent.style.transform = "translateY(100%)";
            sheetContent.style.opacity = "0";
            animateEl(sheetContent, [
                { transform: "translateY(100%)", opacity: 0 },
                { transform: "translateY(0)", opacity: 1 },
            ], { duration: 0.25 });
        },
        navSheetClose(sheetContent) {
            if (!sheetContent) return;
            animateEl(sheetContent, [
                { transform: "translateY(0)", opacity: 1 },
                { transform: "translateY(100%)", opacity: 0 },
            ], { duration: 0.2 });
        },

        /** Modal: scale + fade */
        modalOpen(modalContent) {
            if (!modalContent) return;
            modalContent.style.transform = "scale(0.95)";
            modalContent.style.opacity = "0";
            animateEl(modalContent, [
                { transform: "scale(0.95)", opacity: 0 },
                { transform: "scale(1)", opacity: 1 },
            ], { duration: 0.2 });
        },
        modalClose(modalContent, onComplete) {
            if (!modalContent) {
                if (onComplete) onComplete();
                return;
            }
            animateEl(modalContent, [
                { transform: "scale(1)", opacity: 1 },
                { transform: "scale(0.95)", opacity: 0 },
            ], { duration: 0.15 }).then(() => {
                if (onComplete) onComplete();
            });
        },

        /** Card stagger entrance */
        cardStaggerIn(selector, baseDelay = 0.03) {
            if (prefersReducedMotion()) return;
            const cards = document.querySelectorAll(selector);
            if (!cards.length) return;
            cards.forEach((card, i) => {
                card.style.opacity = "0";
                card.style.transform = "translateY(12px)";
                card.animate(
                    [
                        { opacity: 0, transform: "translateY(12px)" },
                        { opacity: 1, transform: "translateY(0)" },
                    ],
                    {
                        duration: 350,
                        delay: i * baseDelay * 1000,
                        easing: "ease-out",
                        fill: "forwards",
                    }
                );
            });
        },

        /** Button tap feedback */
        buttonTap(btn) {
            if (!btn || prefersReducedMotion()) return;
            btn.animate(
                [{ transform: "scale(1)" }, { transform: "scale(0.97)" }, { transform: "scale(1)" }],
                { duration: 150, easing: "ease-out" }
            );
        },
    };
})();
