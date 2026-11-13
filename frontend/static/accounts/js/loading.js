(() => {
  const overlay = document.querySelector("[data-page-loader]");
  const message = document.querySelector("[data-page-loader-message]");
  if (!overlay || !message) return;

  const hide = () => {
    overlay.hidden = true;
    overlay.setAttribute("aria-hidden", "true");
    document.documentElement.removeAttribute("aria-busy");
  };
  const show = (text = "Loading…") => {
    message.textContent = text;
    overlay.hidden = false;
    overlay.setAttribute("aria-hidden", "false");
    document.documentElement.setAttribute("aria-busy", "true");
  };
  const shouldNavigate = (link, event) => {
    const href = link.getAttribute("href") || "";
    return !event.defaultPrevented
      && event.button === 0
      && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey
      && href && !href.startsWith("#") && !link.target && !link.hasAttribute("download")
      && link.origin === window.location.origin;
  };

  window.addEventListener("pageshow", hide);

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", hide, { once: true });
} else {
  hide();
}
  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[href]");
    if (link && shouldNavigate(link, event)) show("Loading…");
  });
  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (form.dataset.loading === "true") {
      event.preventDefault();
      return;
    }
    if (!form.checkValidity()) return;
    const submitter = event.submitter;
    if (submitter && submitter.dataset.noLoading !== undefined) return;
    let preservedSubmitterField = null;
    if (submitter instanceof HTMLButtonElement && submitter.name) {
      preservedSubmitterField = document.createElement("input");
      preservedSubmitterField.type = "hidden";
      preservedSubmitterField.name = submitter.name;
      preservedSubmitterField.value = submitter.value;
      preservedSubmitterField.dataset.preservedSubmitter = "true";
      form.appendChild(preservedSubmitterField);
    }
    form.dataset.loading = "true";
    form.setAttribute("aria-busy", "true");
    if (submitter instanceof HTMLButtonElement) {
      submitter.dataset.loadingLabel ||= submitter.textContent.trim();
      submitter.disabled = true;
      submitter.textContent = submitter.dataset.loadingText || "Working…";
      submitter.setAttribute("aria-busy", "true");
    }
    show(submitter?.dataset.loadingText || "Loading…");

    // Other form handlers may reject a submission after this shared handler
    // has run. Restore the control in that case so a client-side error never
    // leaves the form permanently busy.
    window.setTimeout(() => {
      if (!event.defaultPrevented) return;
      form.dataset.loading = "false";
      form.removeAttribute("aria-busy");
      preservedSubmitterField?.remove();
      if (submitter instanceof HTMLButtonElement) {
        submitter.disabled = false;
        submitter.textContent = submitter.dataset.loadingLabel || "Submit";
        submitter.removeAttribute("aria-busy");
      }
      hide();
    }, 0);
  });
  window.HireFlowLoading = { hide, show };
})();
