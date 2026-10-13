import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { FBXLoader } from 'three/addons/loaders/FBXLoader.js?v=curve-fix-2';

const $ = id => document.getElementById(id);
const renderer = new THREE.WebGLRenderer({ canvas: $('canvas'), antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setClearColor(0x1b1e23);
renderer.outputColorSpace = THREE.SRGBColorSpace;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 100000);
camera.position.set(240, 160, 280);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.target.set(0, 80, 0);
scene.add(new THREE.HemisphereLight(0xffffff, 0x59616f, 2.3));
const key = new THREE.DirectionalLight(0xffffff, 2.5);
key.position.set(200, 350, 180);
scene.add(key);
let grid = new THREE.GridHelper(1000, 40, 0x59616d, 0x343b44);
scene.add(grid);
let entries = [];
let resources = new Map();
let selected = null;
let object = null;
let wrapper = null;
let helpers = [];
const originalMaterials = new Map();
const grayMaterial = new THREE.MeshStandardMaterial({ color: 0xb3b9c2, roughness: 0.85, metalness: 0, side: THREE.DoubleSide });
let mixer = null;
let action = null;
let playing = false;
let requestId = 0;
let activeUrls = [];
let activeClip = null;
let lastTick = performance.now();

function status(message, error = false) {
  $('status').textContent = message;
  $('status').classList.toggle('error', error);
}

function drawList() {
  const query = $('search').value.toLowerCase();
  const fragment = document.createDocumentFragment();
  for (const entry of entries) {
    if (!entry.path.toLowerCase().includes(query)) continue;
    const button = document.createElement('button');
    button.className = 'file-item' + (entry === selected ? ' active' : '');
    button.title = entry.path;
    const name = document.createElement('span');
    name.textContent = entry.file.name;
    const detail = document.createElement('small');
    detail.textContent = `${(entry.file.size / 1048576).toFixed(1)} MB · ${entry.path.includes('/') ? entry.path.slice(0, entry.path.lastIndexOf('/')) : '本地文件'}`;
    button.append(name, detail);
    button.onclick = () => loadEntry(entry);
    fragment.append(button);
  }
  $('file-list').replaceChildren(fragment);
  $('file-count').textContent = entries.length;
  const visible = entries.filter(entry => entry.path.toLowerCase().includes(query));
  const index = visible.indexOf(selected);
  $('previous-file').disabled = index <= 0 || !$('loading').hidden;
  $('next-file').disabled = index < 0 || index >= visible.length - 1 || !$('loading').hidden;
}

function changeFile(direction) {
  if (!$('loading').hidden) return;
  const query = $('search').value.toLowerCase();
  const visible = entries.filter(entry => entry.path.toLowerCase().includes(query));
  const index = visible.indexOf(selected);
  const next = index >= 0 ? visible[index + direction] : null;
  if (next) loadEntry(next);
}

function addFiles(files) {
  let first = null;
  for (const file of files) {
    const filePath = file.webkitRelativePath || file.name;
    resources.set(filePath.toLowerCase(), file);
    if (!/\.fbx$/i.test(file.name)) continue;
    const existing = entries.find(entry => entry.path === filePath && entry.file.size === file.size && entry.file.lastModified === file.lastModified);
    if (existing) continue;
    const entry = { file, path: filePath };
    entries.push(entry);
    first ||= entry;
  }
  entries.sort((a, b) => a.path.localeCompare(b.path, 'zh-CN', { numeric: true }));
  drawList();
  if (!object && first) loadEntry(first);
  else status(`已添加 · ${entries.length} 个 FBX 文件`);
  if (!entries.length) status('没有找到 FBX 文件', true);
}

function disposeObject(root) {
  const textures = new Set();
  root.traverse(node => {
    node.geometry?.dispose();
    const materials = Array.isArray(node.material) ? node.material : [node.material];
    for (const material of materials) {
      if (!material) continue;
      for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
      material.dispose();
    }
  });
  textures.forEach(texture => texture.dispose());
}

function clearObject() {
  if (mixer) {
    mixer.stopAllAction();
    mixer.uncacheRoot(object);
  }
  for (const helper of helpers) {
    scene.remove(helper);
    helper.geometry.dispose();
    helper.material.dispose();
  }
  helpers = [];
  if (wrapper) {
    for (const [mesh, material] of originalMaterials) mesh.material = material;
    originalMaterials.clear();
    scene.remove(wrapper);
    disposeObject(wrapper);
  }
  for (const url of activeUrls) URL.revokeObjectURL(url);
  activeUrls = [];
  mixer = null;
  action = null;
}

async function loadEntry(entry) {
  const ticket = ++requestId;
  $('loading').hidden = false;
  drawList();
  $('loading').textContent = `读取 ${entry.file.name}…`;
  status('读取 FBX…');
  const urls = [];
  let parsed = null;
  try {
    const buffer = await entry.file.arrayBuffer();
    if (ticket !== requestId) return;
    const manager = new THREE.LoadingManager();
    let missingTextures = 0;
    manager.setURLModifier(url => {
      if (/^(blob:|data:)/i.test(url)) return url;
      const name = decodeURIComponent(url).replace(/\\/g, '/').split('/').pop().toLowerCase();
      const dir = entry.path.includes('/') ? entry.path.slice(0, entry.path.lastIndexOf('/') + 1) : '';
      const file = resources.get((dir + name).toLowerCase()) || [...resources.values()].find(item => item.name.toLowerCase() === name);
      if (file) {
        const blob = URL.createObjectURL(file);
        urls.push(blob);
        return blob;
      }
      missingTextures++;
      return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRz0AAAAASUVORK5CYII=';
    });
    parsed = new FBXLoader(manager).parse(buffer, '');
    clearObject();
    object = parsed;
    activeUrls = urls;
    wrapper = new THREE.Group();
    wrapper.add(object);
    applyAxis();
    scene.add(wrapper);
    wrapper.updateMatrixWorld(true);
    let bones = 0;
    let meshes = 0;
    let triangles = 0;
    object.traverse(node => {
      if (node.isBone) bones++;
      if (node.isMesh) {
        meshes++;
        triangles += (node.geometry.index?.count || node.geometry.attributes.position?.count || 0) / 3;
        if (!node.material) node.material = new THREE.MeshStandardMaterial({ color: 0xb3b9c2, roughness: 0.8 });
        originalMaterials.set(node, node.material);
      }
      if (node.isLight || node.isCamera) node.visible = false;
    });
    if (bones) {
      const helper = new THREE.SkeletonHelper(object);
      helper.material.depthTest = false;
      helper.material.transparent = true;
      helper.material.opacity = 0.85;
      helper.renderOrder = 2;
      scene.add(helper);
      helpers.push(helper);
    }
    mixer = new THREE.AnimationMixer(object);
    selected = entry;
    $('current-name').textContent = entry.file.name;
    $('empty').hidden = true;
    $('model-info').textContent = `${meshes} 个网格 · ${bones} 根骨骼\n${Math.round(triangles).toLocaleString()} 三角面 · ${object.animations.length} 个动画片段`;
    $('clips').replaceChildren();
    object.animations.forEach((clip, index) => {
      const option = document.createElement('option');
      option.value = index;
      option.textContent = clip.name || `片段 ${index + 1}`;
      $('clips').append(option);
    });
    if (!object.animations.length) $('clips').add(new Option('无动画', ''));
    $('clips').disabled = !object.animations.length;
    chooseClip(0);
    updateVisibility();
    frameObject();
    drawList();
    status(`${entry.file.name} · ${object.animations.length ? '已加载' : '无动画曲线，仅显示静态姿势'}${missingTextures ? ' · 缺少贴图，使用白色替代；可选择含贴图的文件夹' : ''}`);
  } catch (error) {
    if (parsed && parsed !== object) disposeObject(parsed);
    if (urls !== activeUrls) urls.forEach(url => URL.revokeObjectURL(url));
    status(`无法读取 ${entry.file.name}：${error.message}`, true);
  } finally {
    if (ticket === requestId) {
      $('loading').hidden = true;
      drawList();
      $('file-list').querySelector('.active')?.scrollIntoView({ block: 'nearest' });
    }
  }
}

function applyAxis() {
  if (!wrapper) return;
  wrapper.rotation.x = $('up-axis').value === 'z' ? -Math.PI / 2 : 0;
  wrapper.updateMatrixWorld(true);
}

function objectBounds() {
  wrapper.updateMatrixWorld(true);
  const bounds = new THREE.Box3();
  const vertex = new THREE.Vector3();
  if ($('show-mesh').checked) {
    object.traverseVisible(node => {
      if (!node.isMesh || !node.geometry.attributes.position) return;
      for (let index = 0; index < node.geometry.attributes.position.count; index++) {
        node.getVertexPosition(index, vertex);
        bounds.expandByPoint(vertex.applyMatrix4(node.matrixWorld));
      }
    });
  }
  if ($('show-bones').checked || bounds.isEmpty()) {
    object.traverse(node => {
      if (node.isBone) bounds.expandByPoint(node.getWorldPosition(vertex));
    });
  }
  if (bounds.isEmpty()) bounds.set(new THREE.Vector3(-50, 0, -50), new THREE.Vector3(50, 100, 50));
  return bounds;
}

function frameObject() {
  if (!object) return;
  const bounds = objectBounds();
  const size = bounds.getSize(new THREE.Vector3());
  const center = bounds.getCenter(new THREE.Vector3());
  const extent = Math.max(size.x, size.y, size.z, 0.1);
  const verticalFov = THREE.MathUtils.degToRad(camera.fov);
  const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * camera.aspect);
  const distance = extent / (2 * Math.tan(Math.min(verticalFov, horizontalFov) / 2)) * 1.6;
  const direction = new THREE.Vector3(1, 0.55, 1).normalize();
  camera.position.copy(center).addScaledVector(direction, distance);
  camera.near = Math.max(extent / 10000, 0.0001);
  camera.far = Math.max(distance * 100, 1000);
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.maxDistance = distance * 50;
  controls.minDistance = extent / 1000;
  controls.update();
  scene.remove(grid);
  grid.geometry.dispose();
  grid.material.dispose();
  grid = new THREE.GridHelper(extent * 5, 40, 0x59616d, 0x343b44);
  grid.position.set(center.x, bounds.min.y, center.z);
  grid.visible = $('show-grid').checked;
  scene.add(grid);
}

function updateVisibility() {
  object?.traverse(node => {
    if (!node.isMesh) return;
    node.visible = $('show-mesh').checked;
    node.material = $('show-materials').checked ? originalMaterials.get(node) : grayMaterial;
  });
  helpers.forEach(helper => { helper.visible = $('show-bones').checked; });
  grid.visible = $('show-grid').checked;
}

function chooseClip(index) {
  mixer?.stopAllAction();
  activeClip = object?.animations[index] || null;
  action = activeClip ? mixer.clipAction(activeClip) : null;
  playing = !!action && activeClip.duration > 0;
  if (action) {
    action.reset().play();
    action.setLoop($('loop').checked ? THREE.LoopRepeat : THREE.LoopOnce, Infinity);
    action.clampWhenFinished = true;
    mixer.update(0);
  }
  $('timeline').max = activeClip?.duration || 1;
  $('time-total').textContent = `${(activeClip?.duration || 0).toFixed(2)}s`;
  for (const id of ['play', 'restart', 'timeline', 'previous-frame', 'next-frame']) $(id).disabled = !action || !activeClip.duration;
  updateTime();
}

function updateTime() {
  const time = action?.time || 0;
  $('timeline').value = time;
  $('time-current').textContent = `${time.toFixed(2)}s`;
  $('play').textContent = playing ? '暂停' : '播放';
  const fps = Number($('fps').value);
  $('frame-number').textContent = `帧 ${Math.round(time * fps)} / ${Math.ceil((activeClip?.duration || 0) * fps)}`;
}

function stepFrame(direction) {
  if (!action || !activeClip.duration) return;
  const fps = Number($('fps').value);
  const frame = action.time * fps;
  const next = direction > 0 ? Math.floor(frame + 0.00001) + 1 : Math.ceil(frame - 0.00001) - 1;
  playing = false;
  seek(Math.max(0, Math.min(next / fps, activeClip.duration)));
}

function seek(time) {
  if (!action) return;
  action.paused = false;
  action.enabled = true;
  action.time = time;
  mixer.update(0);
  object.updateMatrixWorld(true);
  updateTime();
}

function togglePlay() {
  if (!action || !activeClip.duration) return;
  if (!playing && action.time >= activeClip.duration) seek(0);
  playing = !playing;
  updateTime();
}

$('pick-files').onclick = $('empty-pick').onclick = () => $('files').click();
$('pick-folder').onclick = () => $('folder').click();
for (const id of ['files', 'folder']) $(id).onchange = event => {
  addFiles(event.target.files);
  event.target.value = '';
};
$('search').oninput = drawList;
$('frame').onclick = frameObject;
$('up-axis').onchange = () => { applyAxis(); frameObject(); };
for (const id of ['show-mesh', 'show-materials', 'show-bones', 'show-grid']) $(id).onchange = updateVisibility;
$('clips').onchange = () => chooseClip(Number($('clips').value));
$('play').onclick = togglePlay;
$('previous-file').onclick = () => changeFile(-1);
$('next-file').onclick = () => changeFile(1);
$('previous-frame').onclick = () => stepFrame(-1);
$('next-frame').onclick = () => stepFrame(1);
$('fps').onchange = updateTime;
$('restart').onclick = () => seek(0);
$('timeline').oninput = () => { playing = false; seek(Number($('timeline').value)); };
$('loop').onchange = () => {
  if (!action) return;
  action.setLoop($('loop').checked ? THREE.LoopRepeat : THREE.LoopOnce, Infinity);
  action.paused = false;
};
window.addEventListener('keydown', event => {
  if (/INPUT|SELECT|TEXTAREA/.test(event.target.tagName) || event.target.isContentEditable) return;
  if (event.code === 'Space' && event.target.tagName !== 'BUTTON') { event.preventDefault(); togglePlay(); }
  if (event.code === 'KeyF') frameObject();
  if (event.code === 'ArrowLeft') { event.preventDefault(); stepFrame(-1); }
  if (event.code === 'ArrowRight') { event.preventDefault(); stepFrame(1); }
  if (event.code === 'PageUp') { event.preventDefault(); changeFile(-1); }
  if (event.code === 'PageDown') { event.preventDefault(); changeFile(1); }
});
let dragDepth = 0;
window.addEventListener('dragenter', event => { event.preventDefault(); dragDepth++; document.body.classList.add('dragging'); });
window.addEventListener('dragover', event => event.preventDefault());
window.addEventListener('dragleave', () => { if (--dragDepth <= 0) document.body.classList.remove('dragging'); });
window.addEventListener('drop', event => {
  event.preventDefault();
  dragDepth = 0;
  document.body.classList.remove('dragging');
  addFiles(event.dataTransfer.files);
});
new ResizeObserver(() => {
  const width = $('viewport').clientWidth;
  const height = $('viewport').clientHeight;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}).observe($('viewport'));
renderer.setAnimationLoop(now => {
  const delta = Math.min((now - lastTick) / 1000, 0.1);
  lastTick = now;
  if (mixer && playing) {
    action.paused = false;
    mixer.update(delta * Number($('speed').value));
    if (!$('loop').checked && action.time >= activeClip.duration) playing = false;
    updateTime();
  }
  controls.update();
  renderer.render(scene, camera);
});
