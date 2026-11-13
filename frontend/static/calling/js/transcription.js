(() => {
  const controls = document.querySelector("[data-transcription-url]");
  if (!controls || !navigator.mediaDevices || !window.MediaRecorder) return;

  const record = controls.querySelector("[data-record-answer]");
  const stop = controls.querySelector("[data-stop-recording]");
  const transcribe = controls.querySelector("[data-transcribe]");
  const playQuestion = controls.querySelector("[data-play-question]");
  const status = controls.querySelector("[role='status']");
  const form = controls.closest("form");
  const textarea = form.querySelector("textarea[name='answer_text']");
  const csrf = form.querySelector("input[name='csrfmiddlewaretoken']");
  const maxMilliseconds = Number(controls.dataset.maxSeconds || 60) * 1000;
  let recorder;
  let stream;
  let clip;
  let timer;

  playQuestion?.addEventListener("click", async () => {
    playQuestion.disabled = true;
    setStatus("Generating the approved question locally with Piper.");
    try {
      const response = await fetch(controls.dataset.playbackUrl, {
        method: "POST", credentials: "same-origin",
        headers: { "X-CSRFToken": csrf.value, "Accept": "audio/wav" },
      });
      if (!response.ok) throw new Error();
      const objectUrl = URL.createObjectURL(await response.blob());
      const audio = new Audio(objectUrl);
      audio.addEventListener("ended", () => URL.revokeObjectURL(objectUrl), { once: true });
      await audio.play();
      setStatus("Piper playback started. No question audio is stored.");
    } catch (_) {
      setStatus("Question playback is unavailable. Read the displayed question instead.");
    } finally {
      playQuestion.disabled = false;
    }
  });

  const setStatus = (message) => { status.textContent = message; };
  const cleanup = () => {
    window.clearTimeout(timer);
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = undefined;
  };

  record.addEventListener("click", async () => {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/wav"]
        .find((type) => MediaRecorder.isTypeSupported(type));
      recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      const chunks = [];
      recorder.addEventListener("dataavailable", (event) => { if (event.data.size) chunks.push(event.data); });
      recorder.addEventListener("stop", () => {
        clip = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        cleanup();
        record.disabled = false;
        stop.disabled = true;
        transcribe.disabled = !clip.size;
        setStatus("Recording stopped. Select Transcribe, then review and edit the text before submitting.");
      });
      recorder.start();
      record.disabled = true;
      stop.disabled = false;
      transcribe.disabled = true;
      setStatus("Recording in progress. Recording stops automatically at the maximum duration.");
      timer = window.setTimeout(() => recorder?.state === "recording" && recorder.stop(), maxMilliseconds);
    } catch (_) {
      cleanup();
      setStatus("Microphone access is unavailable. You can type your answer instead.");
    }
  });
  stop.addEventListener("click", () => recorder?.state === "recording" && recorder.stop());
  transcribe.addEventListener("click", async () => {
    if (!clip) return;
    transcribe.disabled = true;
    transcribe.setAttribute("aria-busy", "true");
    setStatus("Transcribing locally. Your recording is not saved.");
    window.HireFlowLoading?.show("Transcribing your answer…");
    const body = new FormData();
    body.append("audio", clip, "answer.webm");
    try {
      const response = await fetch(controls.dataset.transcriptionUrl, {
        method: "POST", body, credentials: "same-origin",
        headers: { "X-CSRFToken": csrf.value, "Accept": "application/json" },
      });
      const payload = await response.json();
      if (!response.ok || payload.status !== "success") throw new Error();
      textarea.value = payload.transcript;
      setStatus(`Speech detected in ${payload.vad_segments} segment(s). Transcript ready; review and edit it before submitting.`);
    } catch (_) {
      setStatus("Transcription is unavailable. You can type your answer instead.");
    } finally {
      clip = undefined;
      transcribe.disabled = true;
      transcribe.removeAttribute("aria-busy");
      window.HireFlowLoading?.hide();
    }
  });
})();
