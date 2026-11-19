// Step-by-step assembly viewer: plays each step of assembly-steps.json on assembly.glb.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const root = document.querySelector("#guide");
const base = root.dataset.guide;
const $ = (selector) => document.querySelector(selector);
const STORAGE_KEY = "ashleys-bed:guide-step";
const ACCENT = new THREE.Color("#c2410c");
const DURATION = 1600; // ms
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const CONSUMABLES = { glue: "Wood glue", threadlocker: "Removable threadlocker" };
const IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];

let steps = [];
let current = 0;
let showFinished = false;
let viewer = null; // 3D state; null until the model loads (the panel works without it)

// ---------------------------------------------------------------- storage (may be blocked)
function remember(id) {
  try {
    localStorage.setItem(STORAGE_KEY, id);
  } catch {
    /* private mode or blocked storage: the guide still works, it just forgets the step */
  }
}

function recalled() {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function startIndex() {
  const hash = decodeURIComponent(location.hash.slice(1));
  const find = (id) => steps.findIndex((step) => step.id === id);
  if (hash) return Math.max(find(hash), 0); // unknown deep link -> step 1
  const stored = recalled();
  return stored && find(stored) >= 0 ? find(stored) : 0;
}

// ---------------------------------------------------------------- panel
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function renderPanel(index) {
  const step = steps[index];
  $("#guide-count").textContent = `Step ${index + 1} of ${steps.length}`;
  $(".guide-title").textContent = step.title;
  const hold = $("#guide-hold");
  hold.replaceChildren();
  hold.hidden = !step.hold.length;
  if (step.hold.length) {
    hold.append(element("strong", "HOLD — not ready to build"));
    step.hold.forEach((line) => hold.append(element("p", line)));
  }
  const chips = $("#guide-parts");
  chips.replaceChildren();
  const moved = Object.keys(step.poses).filter((id) => index > 0 && !sameMatrix(steps[index - 1].poses[id], step.poses[id]));
  const named = [...new Set([...step.adds, ...moved])];
  named.forEach((id) => {
    const item = element("li");
    const button = element("button", id, "guide-chip");
    button.type = "button";
    button.addEventListener("click", () => viewer?.flash(id));
    item.append(button);
    chips.append(item);
  });
  if (!named.length) chips.append(element("li", "No new parts in this step.", "guide-none"));
  const needs = $("#guide-needs");
  needs.replaceChildren();
  step.hardware.forEach((item) => needs.append(element("li", `×${item.count}  ${item.name}`)));
  step.consumables.forEach((code) => needs.append(element("li", CONSUMABLES[code] || code, "guide-consumable")));
  $("#guide-needs-wrap").hidden = !needs.children.length;
  const text = $("#guide-text");
  text.replaceChildren(...step.text.map((line) => element("li", line)));
  const warnings = $("#guide-warnings");
  warnings.replaceChildren(...step.warnings.map((line) => element("p", line, "warning")));
  const source = $("#guide-source");
  source.hidden = !step.source;
  source.textContent = step.source ? `Source: ${step.source}` : "";
  $("#guide-svg").src = base + step.svg;
  $("#guide-drawing-holes").hidden = !step.holes_svg;
  if (step.holes_svg) $("#guide-holes-svg").src = base + step.holes_svg;
  else $("#guide-holes-svg").removeAttribute("src");
  $("#guide-back").disabled = index === 0;
  $("#guide-next").disabled = index === steps.length - 1;
}

function sameMatrix(a, b) {
  return !!a && !!b && a.every((value, i) => Math.abs(value - b[i]) < 1e-9);
}

// ---------------------------------------------------------------- navigation
// User navigation brings the 3D view back into sight (on a phone the Next bar sits below the
// text) and moves focus to the new step's title.
function showStep() {
  const stage = $("#guide-stage");
  const top = stage.getBoundingClientRect().top;
  if (top < 0 || top > window.innerHeight / 2) {
    stage.scrollIntoView({ behavior: reducedMotion.matches ? "auto" : "smooth", block: "start" });
  }
  $(".guide-title").focus({ preventScroll: true });
}

function goTo(index, { animate = true, user = true } = {}) {
  index = Math.min(Math.max(index, 0), steps.length - 1);
  viewer?.finish(); // a tween in progress completes before the next step starts
  current = index;
  const id = steps[index].id;
  if (decodeURIComponent(location.hash.slice(1)) !== id) history.replaceState(null, "", `#${id}`);
  remember(id);
  renderPanel(index);
  viewer?.play(index, animate && !reducedMotion.matches);
  if (user) showStep();
}

function wireControls() {
  $("#guide-back").addEventListener("click", () => goTo(current - 1, { animate: false }));
  $("#guide-next").addEventListener("click", () => goTo(current + 1));
  $("#guide-replay").addEventListener("click", () => goTo(current));
  $("#guide-reset").addEventListener("click", () => viewer?.resetCamera());
  $("#guide-finished").addEventListener("change", (event) => {
    showFinished = event.target.checked;
    viewer?.finish();
    viewer?.applyState(current);
    viewer?.resetCamera();
  });
  window.addEventListener("hashchange", () => {
    const index = steps.findIndex((step) => step.id === decodeURIComponent(location.hash.slice(1)));
    if (index !== current) goTo(Math.max(index, 0));
  });
  document.addEventListener("keydown", (event) => {
    if (event.target.closest("input, textarea, select, dialog")) return;
    if (event.key === "ArrowRight") goTo(current + 1);
    if (event.key === "ArrowLeft") goTo(current - 1, { animate: false });
  });
  const panel = $("#guide-panel");
  let touch = null;
  panel.addEventListener("touchstart", (event) => {
    touch = event.touches.length === 1 ? { x: event.touches[0].clientX, y: event.touches[0].clientY } : null;
  }, { passive: true });
  panel.addEventListener("touchend", (event) => {
    if (!touch) return;
    const dx = event.changedTouches[0].clientX - touch.x;
    const dy = event.changedTouches[0].clientY - touch.y;
    touch = null;
    if (Math.abs(dx) > 60 && Math.abs(dy) < 40) goTo(dx < 0 ? current + 1 : current - 1, { animate: dx < 0 });
  }, { passive: true });
  const zoom = $("#guide-zoom");
  for (const [button, image] of [["#guide-drawing-step", "#guide-svg"], ["#guide-drawing-holes", "#guide-holes-svg"]]) {
    $(button).addEventListener("click", () => {
      $("#guide-zoom-img").src = $(image).src;
      $("#guide-zoom-img").alt = $(image).alt;
      if (typeof zoom.showModal === "function") zoom.showModal();
      else window.open($(image).src, "_blank");
    });
  }
  zoom.addEventListener("click", (event) => {
    if (event.target === zoom || event.target.id === "guide-zoom-img") zoom.close();
  });
}

// ---------------------------------------------------------------- 3D viewer
function createViewer(gltf) {
  const canvas = $("#guide-canvas");
  const stage = $("#guide-stage");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#f3f5f8");
  scene.add(new THREE.HemisphereLight("#ffffff", "#9aa5b1", 2.2));
  const sun = new THREE.DirectionalLight("#ffffff", 1.6);
  sun.position.set(-3, 5, 4);
  scene.add(sun);
  const camera = new THREE.PerspectiveCamera(40, 1, 0.05, 60);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.screenSpacePanning = true;
  scene.add(gltf.scene);

  const added = new Set(steps.flatMap((step) => step.adds));
  const hardwareStep = new Map();
  steps.forEach((step, i) => step.hardware.forEach((item) => item.nodes.forEach((node) => {
    if (!hardwareStep.has(node)) hardwareStep.set(node, { step: i, item });
  })));
  const firstStep = new Map();
  steps.forEach((step, i) => step.adds.forEach((id) => firstStep.set(id, i)));
  const nodes = new Map();
  gltf.scene.traverse((object) => {
    if (!object.isMesh) return;
    object.material = object.material.clone();
    object.matrixAutoUpdate = false;
    object.userData.finish = object.material.color.clone();
    object.userData.centre = new THREE.Box3().setFromBufferAttribute(object.geometry.attributes.position)
      .getCenter(new THREE.Vector3());
    nodes.set(object.name, object);
  });
  const context = [...nodes.keys()].filter((name) => !added.has(name) && !hardwareStep.has(name));
  const identity = new THREE.Matrix4();
  let tween = null;
  let cameraTween = null;

  function poseOf(name, index) {
    const pose = steps[index]?.poses[name];
    return pose ? new THREE.Matrix4().fromArray(pose) : identity.clone();
  }

  function setColour(object, colour) {
    object.material.color.copy(colour);
  }

  function applyState(index) {
    for (const [name, object] of nodes) {
      setColour(object, object.userData.finish);
      object.material.emissive?.setRGB(0, 0, 0);
      if (showFinished) {
        object.visible = true;
        object.matrix.identity();
        continue;
      }
      if (context.includes(name)) {
        object.visible = true;
        object.matrix.identity();
      } else if (hardwareStep.has(name)) {
        object.visible = hardwareStep.get(name).step <= index;
        object.matrix.identity();
      } else {
        object.visible = firstStep.has(name) && firstStep.get(name) <= index;
        object.matrix.copy(poseOf(name, index));
      }
    }
  }

  // What the camera frames: parts in place at this step plus the parts this step adds or drills
  // (a side waiting on the bench is left out unless this step works on it).
  function focusBox(index) {
    const step = steps[index];
    const box = new THREE.Box3();
    const ids = showFinished ? [...firstStep.keys()] : Object.keys(step.poses).filter((id) =>
      step.adds.includes(id) || step.drills.includes(id) || sameMatrix(step.poses[id], IDENTITY));
    for (const id of ids) {
      const object = nodes.get(id);
      if (!object) continue;
      const local = new THREE.Box3().setFromBufferAttribute(object.geometry.attributes.position);
      box.union(local.applyMatrix4(showFinished ? identity : poseOf(id, index)));
    }
    return box.isEmpty() ? new THREE.Box3().setFromObject(gltf.scene) : box;
  }

  function cameraFor(index) {
    const view = steps[index].camera;
    const sphere = focusBox(index).getBoundingSphere(new THREE.Sphere());
    const az = THREE.MathUtils.degToRad(view.azimuth);
    const el = THREE.MathUtils.degToRad(view.elevation);
    const vfov = THREE.MathUtils.degToRad(camera.fov);
    const hfov = 2 * Math.atan(Math.tan(vfov / 2) * camera.aspect);
    const distance = Math.max(sphere.radius / Math.sin(Math.min(vfov, hfov) / 2) * 1.05, 0.6);
    // azimuth 0 looks from the room side; positive turns toward the bookcase's outer end
    const offset = new THREE.Vector3(-Math.sin(az) * Math.cos(el), Math.sin(el), Math.cos(az) * Math.cos(el));
    return { position: sphere.center.clone().addScaledVector(offset, distance), target: sphere.center.clone() };
  }

  function moveCamera(index, animate) {
    const goal = cameraFor(index);
    if (!animate) {
      camera.position.copy(goal.position);
      controls.target.copy(goal.target);
      cameraTween = null;
      controls.update();
      return;
    }
    cameraTween = { start: performance.now(), from: camera.position.clone(), fromTarget: controls.target.clone(), ...goal };
  }

  // Animated pieces for step `index`, starting from the state after step index - 1.
  function play(index, animate) {
    const moved = [];
    for (const [name, object] of nodes) {
      if (!firstStep.has(name)) continue;
      const before = index > 0 && firstStep.get(name) < index ? poseOf(name, index - 1) : null;
      const after = poseOf(name, index);
      if (before && !before.equals(after)) moved.push({ object, before, after });
    }
    const step = steps[index];
    const fresh = step.adds.map((id) => nodes.get(id)).filter(Boolean);
    const travel = new THREE.Vector3().fromArray(step.move).normalize();
    const hardware = step.hardware.flatMap((item) =>
      item.nodes.map((name) => ({ object: nodes.get(name), item })).filter((entry) => entry.object));
    applyState(index);
    moveCamera(index, animate);
    if (!animate || showFinished) {
      tween = null;
      return;
    }
    tween = { start: performance.now(), moved, fresh, travel, hardware };
    renderTween(0);
  }

  const ease = (t) => (t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t));
  const window01 = (t, a, b) => ease((t - a) / (b - a));
  const position = new THREE.Vector3();
  const quaternion = new THREE.Quaternion();
  const scale = new THREE.Vector3(1, 1, 1);

  function renderTween(t) {
    const { moved, fresh, travel, hardware } = tween;
    // 1. parts already in the scene move to this step's pose (e.g. a side lifted off the bench)
    for (const { object, before, after } of moved) {
      const k = window01(t, 0, 0.45);
      const p0 = new THREE.Vector3(), q0 = new THREE.Quaternion(), p1 = new THREE.Vector3(), q1 = new THREE.Quaternion();
      before.decompose(p0, q0, new THREE.Vector3());
      after.decompose(p1, q1, new THREE.Vector3());
      position.lerpVectors(p0, p1, k);
      quaternion.slerpQuaternions(q0, q1, k);
      object.matrix.compose(position, quaternion, scale);
      setColour(object, ACCENT.clone().lerp(object.userData.finish, window01(t, 0.8, 1)));
    }
    // 2. dowels slide into their holes
    // 3. the new panel slides in along `move`
    // 4. screws advance and spin
    for (const { object, item } of hardware) {
      const axis = new THREE.Vector3().fromArray(item.axis || travel.toArray());
      const [a, b, reach] = item.phase === "dowel" ? [0.1, 0.4, 0.05] : [0.7, 0.95, 0.06];
      const k = window01(t, a, b);
      object.visible = t >= a;
      const shift = axis.clone().multiplyScalar(-(1 - k) * reach);
      const centre = object.userData.centre;
      const spin = item.phase === "screw" ? (1 - k) * Math.PI * 6 : 0;
      object.matrix.makeTranslation(shift.x + centre.x, shift.y + centre.y, shift.z + centre.z)
        .multiply(new THREE.Matrix4().makeRotationAxis(axis, spin))
        .multiply(new THREE.Matrix4().makeTranslation(-centre.x, -centre.y, -centre.z));
    }
    for (const object of fresh) {
      const k = window01(t, 0.35, 0.75);
      const pose = poseOf(object.name, current);
      const shift = travel.clone().multiplyScalar(-(1 - k) * 0.25);
      object.matrix.makeTranslation(shift.x, shift.y, shift.z).multiply(pose);
      object.visible = t >= 0.3;
      setColour(object, ACCENT.clone().lerp(object.userData.finish, window01(t, 0.8, 1)));
    }
  }

  function finish() {
    if (tween) {
      renderTween(1);
      tween = null;
      applyState(current);
    }
    if (cameraTween) {
      camera.position.copy(cameraTween.position);
      controls.target.copy(cameraTween.target);
      cameraTween = null;
    }
  }

  function flash(id) {
    const object = nodes.get(id);
    if (!object || !object.visible || !object.material.emissive) return;
    object.material.emissive.copy(ACCENT);
    setTimeout(() => object.material.emissive.setRGB(0, 0, 0), 700);
  }

  function resize() {
    const { width, height } = stage.getBoundingClientRect();
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(stage);
  resize();

  // double-tap (touch) or double-click resets the view
  let lastTap = 0;
  canvas.addEventListener("touchend", (event) => {
    if (event.touches.length) return;
    const now = performance.now();
    if (now - lastTap < 300) moveCamera(current, !reducedMotion.matches);
    lastTap = now;
  });
  canvas.addEventListener("dblclick", () => moveCamera(current, !reducedMotion.matches));
  controls.addEventListener("start", () => { cameraTween = null; });

  renderer.setAnimationLoop((now) => {
    if (tween) {
      const t = (now - tween.start) / DURATION;
      if (t >= 1) finish();
      else renderTween(t);
    }
    if (cameraTween) {
      const k = ease((now - cameraTween.start) / (DURATION * 0.6));
      camera.position.lerpVectors(cameraTween.from, cameraTween.position, k);
      controls.target.lerpVectors(cameraTween.fromTarget, cameraTween.target, k);
      if (k >= 1) cameraTween = null;
    }
    controls.update();
    renderer.render(scene, camera);
  });

  return {
    play, finish, flash, applyState,
    resetCamera: () => moveCamera(current, !reducedMotion.matches),
    debug: () => ({ tween: !!tween, visible: [...nodes].filter(([, o]) => o.visible).map(([n]) => n), count: nodes.size,
      camera: camera.position.toArray().map((v) => +v.toFixed(3)) }),
  };
}

// ---------------------------------------------------------------- start
async function start() {
  wireControls();
  const status = $("#guide-status");
  try {
    const response = await fetch(base + "assembly-steps.json");
    if (!response.ok) throw new Error(`steps: HTTP ${response.status}`);
    steps = await response.json();
  } catch (error) {
    status.textContent = "The steps could not be loaded. Check your connection and reload.";
    console.warn(error);
    return;
  }
  current = startIndex();
  goTo(current, { animate: false, user: false });
  $("#guide-stage").scrollIntoView({ block: "start" }); // the page opens on the 3D view, as on a phone it fills the top
  try {
    const gltf = await new GLTFLoader().loadAsync(base + "assembly.glb");
    viewer = createViewer(gltf);
    viewer.play(current, false);
    status.hidden = true;
  } catch (error) {
    status.textContent = "The 3D view is not available on this device. The drawings below show each step.";
    console.warn(error);
  }
  window.assemblyGuide = { goTo, state: () => ({ current, id: steps[current].id, ...(viewer?.debug() || {}) }) };
}

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch((error) => console.warn("Offline cache unavailable", error));
}
start();
