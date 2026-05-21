"use client";

import { useEffect, useRef } from "react";
import type { RefObject } from "react";

const FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "textarea:not([disabled])",
  "select:not([disabled])",
  "[tabindex]:not([tabindex='-1'])"
].join(",");

/**
 * Trap keyboard focus inside `containerRef` while `active` is true.
 *
 * Rules:
 *  - On mount, the previously-focused element is captured and the first
 *    focusable element inside the container receives focus. If the
 *    container has nothing focusable, focus moves to the container
 *    itself (must have `tabindex="-1"`).
 *  - `Tab` and `Shift+Tab` wrap inside the container.
 *  - On unmount the previously-focused element regains focus, so the
 *    operator's keyboard position is restored.
 *
 * This is the minimal real implementation — no `aria-hidden` siblings,
 * no inert poly-fill — which is enough for the cockpit's modals because
 * they cover the rest of the UI with a backdrop that blocks pointer
 * events and the focus loop covers keyboard.
 */
export function useFocusTrap(
  containerRef: RefObject<HTMLElement | null>,
  active: boolean
): void {
  const previousFocus = useRef<Element | null>(null);

  useEffect(() => {
    if (!active) return;
    const container = containerRef.current;
    if (!container) return;

    previousFocus.current = document.activeElement;

    const focusables = (): HTMLElement[] =>
      Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (el) => el.offsetParent !== null
      );

    const list = focusables();
    if (list.length > 0) {
      list[0].focus();
    } else if (typeof container.focus === "function") {
      container.focus();
    }

    function onKeydown(event: KeyboardEvent) {
      if (event.key !== "Tab") return;
      const scope = containerRef.current;
      if (!scope) return;
      const items = focusables();
      if (items.length === 0) {
        event.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const current = document.activeElement as HTMLElement | null;
      if (event.shiftKey) {
        if (current === first || !scope.contains(current)) {
          event.preventDefault();
          last.focus();
        }
      } else if (current === last || !scope.contains(current)) {
        event.preventDefault();
        first.focus();
      }
    }

    container.addEventListener("keydown", onKeydown);
    return () => {
      container.removeEventListener("keydown", onKeydown);
      const previous = previousFocus.current as HTMLElement | null;
      if (previous && typeof previous.focus === "function") {
        previous.focus();
      }
    };
  }, [active, containerRef]);
}
