import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

let scene, camera, controls, renderer, textureLoader;
const textureCache = {};

function apiBasePath() {
  if (typeof window === 'undefined') return '';
  return String(window.__OBLLOMOV_API_BASE__ || '').replace(/\/$/, '');
}

export function apiUrl(path) {
  if (path == null) return path;
  const s = String(path);
  if (s.startsWith('http://') || s.startsWith('https://')) return s;
  return apiBasePath() + (s.startsWith('/') ? s : `/${s}`);
}

export function initViewer() {
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.shadowMap.enabled = true;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.5;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  document.body.appendChild(renderer.domElement);

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x87ceeb);

  camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 100);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
  scene.add(ambientLight);

  const dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
  dirLight.position.set(5, 10, 5);
  dirLight.castShadow = true;
  scene.add(dirLight);

  const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 0.4);
  scene.add(hemiLight);

  textureLoader = new THREE.TextureLoader();

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  return { scene, camera, controls, renderer };
}

export function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

export function positionCamera(rooms) {
  let centerX = 0, centerZ = 0, count = 0;
  for (const room of rooms) {
    for (const p of (room.floor_polygon || [])) {
      centerX += p.x;
      centerZ += p.z;
      count++;
    }
  }
  centerX /= count || 1;
  centerZ /= count || 1;
  controls.target.set(centerX, 1.0, centerZ);
  camera.position.set(centerX - 5, 8, centerZ - 5);
  controls.update();
}

function loadTexture(materialName) {
  if (textureCache[materialName]) return textureCache[materialName];
  const tex = textureLoader.load(apiUrl(`/materials/${materialName}.png`));
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(2, 2);
  textureCache[materialName] = tex;
  return tex;
}

function makeMaterial(matInfo, repeatX = 2, repeatY = 2) {
  const params = { side: THREE.DoubleSide };
  if (matInfo && matInfo.name) {
    const tex = loadTexture(matInfo.name);
    tex.repeat.set(repeatX, repeatY);
    params.map = tex;
  }
  if (matInfo && matInfo.color) {
    params.color = new THREE.Color(matInfo.color.r, matInfo.color.g, matInfo.color.b);
  }
  return new THREE.MeshStandardMaterial(params);
}

export function buildFloor(room) {
  const polygon = room.floor_polygon;
  if (!polygon || polygon.length < 3) return;

  const shape = new THREE.Shape();
  shape.moveTo(polygon[0].x, -polygon[0].z);
  for (let i = 1; i < polygon.length; i++) {
    shape.lineTo(polygon[i].x, -polygon[i].z);
  }
  shape.closePath();

  const geometry = new THREE.ShapeGeometry(shape);
  geometry.rotateX(-Math.PI / 2);

  const mat = makeMaterial(room.floor_material, 3, 3);
  const mesh = new THREE.Mesh(geometry, mat);
  mesh.receiveShadow = true;
  mesh.position.y = 0.000;
  scene.add(mesh);
}

function computeWallUVs(poly) {
  const uvs = [];
  let minU = Infinity, maxU = -Infinity, minV = Infinity, maxV = -Infinity;

  for (const p of poly) {
    const u = Math.abs(poly[0].x - poly[2].x) > Math.abs(poly[0].z - poly[2].z) ? p.x : p.z;
    const v = p.y;
    uvs.push(u, v);
    minU = Math.min(minU, u);
    maxU = Math.max(maxU, u);
    minV = Math.min(minV, v);
    maxV = Math.max(maxV, v);
  }

  const rangeU = maxU - minU || 1;
  const rangeV = maxV - minV || 1;
  for (let i = 0; i < uvs.length; i += 2) {
    uvs[i] = (uvs[i] - minU) / rangeU;
    uvs[i + 1] = (uvs[i + 1] - minV) / rangeV;
  }
  return uvs;
}

export function buildWall(wall) {
  const poly = wall.polygon;
  if (!poly || poly.length < 3) return;

  const vertices = [];
  for (const p of poly) {
    vertices.push(p.x, p.y, p.z);
  }

  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(vertices);
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

  if (poly.length === 4) {
    geometry.setIndex([0, 1, 2, 0, 2, 3]);
  } else {
    const indices = [];
    for (let i = 1; i < poly.length - 1; i++) {
      indices.push(0, i, i + 1);
    }
    geometry.setIndex(indices);
  }
  geometry.computeVertexNormals();

  const uvs = computeWallUVs(poly);
  geometry.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(uvs), 2));

  const matName = wall.material ? wall.material.name : null;
  const mat = makeMaterial({ name: matName }, wall.width / 2, wall.height / 2);
  const mesh = new THREE.Mesh(geometry, mat);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  scene.add(mesh);
}

function loadCroppedDoorTexture(url, callback) {
  const img = new Image();
  img.crossOrigin = 'anonymous';
  img.onload = () => {
    const c = document.createElement('canvas');
    c.width = img.naturalWidth;
    c.height = img.naturalHeight;
    const ctx = c.getContext('2d');
    ctx.drawImage(img, 0, 0);
    const data = ctx.getImageData(0, 0, c.width, c.height).data;

    let minX = c.width, minY = c.height, maxX = 0, maxY = 0;
    for (let y = 0; y < c.height; y++) {
      for (let x = 0; x < c.width; x++) {
        if (data[(y * c.width + x) * 4 + 3] > 25) {
          if (x < minX) minX = x;
          if (x > maxX) maxX = x;
          if (y < minY) minY = y;
          if (y > maxY) maxY = y;
        }
      }
    }

    if (maxX < minX) return;

    const cropW = maxX - minX + 1;
    const cropH = maxY - minY + 1;
    const cropped = document.createElement('canvas');
    cropped.width = cropW;
    cropped.height = cropH;
    cropped.getContext('2d').drawImage(img, minX, minY, cropW, cropH, 0, 0, cropW, cropH);

    const tex = new THREE.CanvasTexture(cropped);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.minFilter = THREE.LinearFilter;
    tex.magFilter = THREE.LinearFilter;
    callback(tex);
  };
  img.src = url;
}

export function buildDoor(door) {
  const hp = door.hole_polygon;
  if (!hp || hp.length < 2) return;

  const seg = door.door_segment;
  const midX = (seg.v1.x + seg.v2.x) / 2;
  const midZ = (seg.v1.z + seg.v2.z) / 2;

  const width = Math.sqrt(
    Math.pow(seg.v2.x - seg.v1.x, 2) + Math.pow(seg.v2.z - seg.v1.z, 2)
  );
  const height = hp[1].y - hp[0].y;

  const dx = seg.v2.x - seg.v1.x;
  const dz = seg.v2.z - seg.v1.z;
  const rotY = Math.atan2(-dz, dx);

  const group = new THREE.Group();
  group.position.set(midX, hp[0].y, midZ);
  group.rotation.y = rotY;

  const frameMat = new THREE.MeshStandardMaterial({ color: 0x5c3a1e, roughness: 0.6 });
  const frameThick = 0.06;
  const frameDepth = 0.15;

  const topBar = new THREE.Mesh(
    new THREE.BoxGeometry(width + frameThick * 2, frameThick, frameDepth),
    frameMat
  );
  topBar.position.y = height + frameThick / 2;
  group.add(topBar);

  const sideGeo = new THREE.BoxGeometry(frameThick, height, frameDepth);
  for (const sign of [-1, 1]) {
    const side = new THREE.Mesh(sideGeo, frameMat);
    side.position.set(sign * (width / 2 + frameThick / 2), height / 2, 0);
    group.add(side);
  }

  const panelGeo = new THREE.PlaneGeometry(width, height);
  const panelOffset = frameDepth / 2 + 0.005;

  const frontMat = new THREE.MeshStandardMaterial({ roughness: 0.5 });
  const front = new THREE.Mesh(panelGeo, frontMat);
  front.position.set(0, height / 2, panelOffset);
  front.castShadow = true;
  group.add(front);

  const backMat = new THREE.MeshStandardMaterial({ roughness: 0.5 });
  const back = new THREE.Mesh(panelGeo, backMat);
  back.position.set(0, height / 2, -panelOffset);
  back.rotation.y = Math.PI;
  back.castShadow = true;
  group.add(back);

  loadCroppedDoorTexture(apiUrl(`/doors/${door.asset_id}.png`), (tex) => {
    frontMat.map = tex;
    frontMat.needsUpdate = true;
    const backTex = tex.clone();
    backTex.needsUpdate = true;
    backMat.map = backTex;
    backMat.needsUpdate = true;
  });

  scene.add(group);
}

export function buildWindow(win) {
  const hp = win.hole_polygon;
  if (!hp || hp.length < 2) return;

  const seg = win.window_segment;
  const midX = (seg.v1.x + seg.v2.x) / 2;
  const midZ = (seg.v1.z + seg.v2.z) / 2;

  const width = Math.sqrt(
    Math.pow(seg.v2.x - seg.v1.x, 2) + Math.pow(seg.v2.z - seg.v1.z, 2)
  );
  const height = hp[1].y - hp[0].y;

  const dx = seg.v2.x - seg.v1.x;
  const dz = seg.v2.z - seg.v1.z;
  const rotY = Math.atan2(-dz, dx);

  const group = new THREE.Group();
  group.position.set(midX, hp[0].y + height / 2, midZ);
  group.rotation.y = rotY;

  const frameMat = new THREE.MeshStandardMaterial({ color: 0xe8e8e8, roughness: 0.3, metalness: 0.2 });
  const frameThick = 0.04;
  const frameDepth = 0.1;

  const outerTop = new THREE.Mesh(new THREE.BoxGeometry(width + frameThick * 2, frameThick, frameDepth), frameMat);
  outerTop.position.y = height / 2 + frameThick / 2;
  group.add(outerTop);

  const outerBot = new THREE.Mesh(new THREE.BoxGeometry(width + frameThick * 2, frameThick, frameDepth), frameMat);
  outerBot.position.y = -height / 2 - frameThick / 2;
  group.add(outerBot);

  const sideGeo = new THREE.BoxGeometry(frameThick, height, frameDepth);
  for (const sign of [-1, 1]) {
    const side = new THREE.Mesh(sideGeo, frameMat);
    side.position.x = sign * (width / 2 + frameThick / 2);
    group.add(side);
  }

  const assetId = win.asset_id || '';
  let cols = 1;
  let rows = 1;
  if (assetId.includes('Double') || assetId.includes('Slider') || assetId.includes('96')) cols = 2;
  if (assetId.includes('Hung')) rows = 2;
  if (assetId.includes('Bay')) cols = 3;

  const mullionThick = 0.025;
  if (cols > 1) {
    for (let c = 1; c < cols; c++) {
      const x = -width / 2 + (width / cols) * c;
      const mullion = new THREE.Mesh(new THREE.BoxGeometry(mullionThick, height, frameDepth * 0.8), frameMat);
      mullion.position.x = x;
      group.add(mullion);
    }
  }
  if (rows > 1) {
    for (let r = 1; r < rows; r++) {
      const y = -height / 2 + (height / rows) * r;
      const rail = new THREE.Mesh(new THREE.BoxGeometry(width, mullionThick, frameDepth * 0.8), frameMat);
      rail.position.y = y;
      group.add(rail);
    }
  }

  const glassMat = new THREE.MeshPhysicalMaterial({
    color: 0x88ccff,
    transparent: true,
    opacity: 0.25,
    roughness: 0.05,
    metalness: 0.05,
    transmission: 0.9,
    side: THREE.DoubleSide,
  });
  const glass = new THREE.Mesh(new THREE.PlaneGeometry(width, height), glassMat);
  glass.position.z = 0.02;
  group.add(glass);

  const sillMat = new THREE.MeshStandardMaterial({ color: 0xd0d0d0, roughness: 0.4 });
  const sill = new THREE.Mesh(new THREE.BoxGeometry(width + 0.1, 0.03, 0.18), sillMat);
  sill.position.y = -height / 2 - 0.015;
  sill.position.z = 0.05;
  group.add(sill);

  scene.add(group);
}

export async function buildObject(obj) {
  const resp = await fetch(apiUrl(`/mesh/${obj.asset_id}`));
  if (!resp.ok) {
    console.warn(`Failed to load mesh ${obj.asset_id}: ${resp.status}`);
    return;
  }
  const mesh = await resp.json();

  const positions = new Float32Array(mesh.vertices.flat());
  const normals = new Float32Array(mesh.normals.flat());
  const uvs = new Float32Array(mesh.uvs.flat());
  const indices = mesh.triangles;

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
  geometry.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
  geometry.setIndex(indices);

  const albedo = textureLoader.load(apiUrl(mesh.albedoUrl));
  albedo.flipY = false;
  albedo.colorSpace = THREE.SRGBColorSpace;

  const normal = textureLoader.load(apiUrl(mesh.normalUrl));
  normal.flipY = false;

  const emission = textureLoader.load(apiUrl(mesh.emissionUrl));
  emission.flipY = false;
  emission.colorSpace = THREE.SRGBColorSpace;

  const mat = new THREE.MeshStandardMaterial({
    map: albedo,
    normalMap: normal,
    emissiveMap: emission,
    emissive: new THREE.Color(0xffffff),
    side: THREE.DoubleSide,
  });

  geometry.computeBoundingBox();
  const center = new THREE.Vector3();
  geometry.boundingBox.getCenter(center);
  geometry.translate(-center.x, -center.y, -center.z);

  const object3d = new THREE.Mesh(geometry, mat);
  object3d.userData.objectId = obj.id;
  object3d.position.set(obj.position.x, obj.position.y, obj.position.z);
  object3d.rotation.order = 'YXZ';
  object3d.rotation.set(
    THREE.MathUtils.degToRad(obj.rotation.x),
    THREE.MathUtils.degToRad(obj.rotation.y),
    THREE.MathUtils.degToRad(obj.rotation.z)
  );
  object3d.castShadow = true;
  object3d.receiveShadow = true;
  scene.add(object3d);
  return object3d;
}

export function wallDedupeKey(wall) {
  const poly = wall.polygon;
  return poly.map(p => `${p.x.toFixed(2)},${p.y.toFixed(2)},${p.z.toFixed(2)}`).sort().join('|');
}
