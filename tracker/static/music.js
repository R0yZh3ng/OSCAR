"use strict";
// Background music: loops whatever audio files are in data/music/ (see tracker/app.py).
// It only plays while this page is visible, so with several tracker tabs open just the shown one
// is heard. ?music=0 turns it off; the on-screen button remembers mute.
(async () => {
  const VOLUME = 0.25;
  if (new URLSearchParams(location.search).get("music") === "0") return;
  const tracks = await (await fetch("/api/music")).json();
  if (!tracks.length) return;

  const audio = new Audio(), button = document.getElementById("music");
  let index = Math.floor(Math.random() * tracks.length), failures = 0;
  let muted = localStorage.getItem("oscar-muted") === "1";
  audio.volume = VOLUME;

  function load() { audio.src = "/music/" + encodeURIComponent(tracks[index]); }
  function sync() {
    button.textContent = muted ? "♪ Music off" : audio.paused ? "♪ Play music" : "♪ Music on";
    button.setAttribute("aria-pressed", String(!muted));
  }
  // browsers may refuse to autoplay until the first tap; the kiosk allows it with a Chromium flag
  function update() {
    if (muted || document.hidden) audio.pause();
    else audio.play().catch(sync);
    sync();
  }
  function next() { index = (index + 1) % tracks.length; load(); update(); }

  audio.addEventListener("ended", next);
  audio.addEventListener("error", () => { if (++failures < tracks.length) next(); });
  audio.addEventListener("playing", () => { failures = 0; sync(); });
  audio.addEventListener("pause", sync);
  button.addEventListener("click", () => {
    muted = !muted && !audio.paused;  // a blocked "Play music" tap starts it rather than muting
    localStorage.setItem("oscar-muted", muted ? "1" : "0");
    update();
  });
  document.addEventListener("visibilitychange", update);
  document.addEventListener("pointerdown", (e) => { if (e.target !== button && audio.paused) update(); });

  button.hidden = false;
  load();
  update();
})();
