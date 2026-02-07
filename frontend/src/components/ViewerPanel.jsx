import React, { useRef, useEffect, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader';
import { useApp } from '../context/AppContext';
import './ViewerPanel.css';

const ViewerPanel = ({ modelToLoad, onModelLoaded }) => {
  const containerRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const controlsRef = useRef(null);
  const [hasModels, setHasModels] = useState(false);
  const { addSceneObject, sceneObjects, addChatMessage } = useApp();

  useEffect(() => {
    if (!containerRef.current) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xF4F3EE);
    scene.fog = new THREE.Fog(0xF4F3EE, 10, 50);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(
      50,
      containerRef.current.clientWidth / containerRef.current.clientHeight,
      0.1,
      1000
    );
    camera.position.set(5, 5, 5);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(containerRef.current.clientWidth, containerRef.current.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    containerRef.current.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.screenSpacePanning = false;
    controls.minDistance = 1;
    controls.maxDistance = 50;
    controls.maxPolarAngle = Math.PI / 2;
    controlsRef.current = controls;

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(10, 10, 5);
    directionalLight.castShadow = true;
    directionalLight.shadow.mapSize.width = 2048;
    directionalLight.shadow.mapSize.height = 2048;
    scene.add(directionalLight);

    const hemisphereLight = new THREE.HemisphereLight(0xffffff, 0x444444, 0.4);
    scene.add(hemisphereLight);

    const gridHelper = new THREE.GridHelper(20, 20, 0x888888, 0xcccccc);
    scene.add(gridHelper);

    const handleResize = () => {
      if (!containerRef.current) return;
      camera.aspect = containerRef.current.clientWidth / containerRef.current.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(containerRef.current.clientWidth, containerRef.current.clientHeight);
    };
    window.addEventListener('resize', handleResize);

    const animate = () => {
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      window.removeEventListener('resize', handleResize);
      renderer.dispose();
      containerRef.current?.removeChild(renderer.domElement);
    };
  }, []);

  useEffect(() => {
    sceneObjects.forEach(obj => {
      if (obj.model) {
        obj.model.visible = obj.visible;
      }
    });
  }, [sceneObjects]);

  useEffect(() => {
    if (modelToLoad && sceneRef.current) {
      loadModel(modelToLoad.url, modelToLoad.filename);
    }
  }, [modelToLoad]);

  const loadModel = (url, filename) => {
    const scene = sceneRef.current;
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    
    const extension = filename.split('.').pop().toLowerCase();
    
    if (extension === 'glb' || extension === 'gltf') {
      const loader = new GLTFLoader();
      loader.load(
        url,
        (gltf) => {
          const model = gltf.scene;
          
          const box = new THREE.Box3().setFromObject(model);
          const center = box.getCenter(new THREE.Vector3());
          const size = box.getSize(new THREE.Vector3());
          
          const maxDim = Math.max(size.x, size.y, size.z);
          const scale = 4 / maxDim;
          model.scale.multiplyScalar(scale);
          
          model.position.x = -center.x * scale;
          model.position.y = -box.min.y * scale;
          model.position.z = -center.z * scale;
          
          scene.add(model);
          
          const sceneObj = {
            id: Date.now(),
            name: filename,
            model: model,
            visible: true,
            position: model.position.toArray(),
            rotation: model.rotation.toArray(),
            scale: model.scale.toArray()
          };
          
          addSceneObject(sceneObj);
          setHasModels(true);
          
          camera.position.set(5, 5, 5);
          controls.target.set(0, size.y * scale / 2, 0);
          controls.update();
          
          addChatMessage('assistant', `Модель "${filename}" успешно добавлена на сцену!`);
          
          if (onModelLoaded) {
            onModelLoaded();
          }
        },
        (progress) => {
          console.log('Loading progress:', progress);
        },
        (error) => {
          console.error('Error loading model:', error);
          addChatMessage('assistant', `Ошибка загрузки модели: ${error.message}`);
        }
      );
    } else if (extension === 'obj') {
      const loader = new OBJLoader();
      loader.load(
        url,
        (obj) => {
          obj.traverse((child) => {
            if (child.isMesh) {
              child.material = new THREE.MeshPhongMaterial({ 
                color: 0x888888,
                side: THREE.DoubleSide
              });
            }
          });
          
          const box = new THREE.Box3().setFromObject(obj);
          const center = box.getCenter(new THREE.Vector3());
          const size = box.getSize(new THREE.Vector3());
          
          const maxDim = Math.max(size.x, size.y, size.z);
          const scale = 4 / maxDim;
          obj.scale.multiplyScalar(scale);
          
          obj.position.x = -center.x * scale;
          obj.position.y = -box.min.y * scale;
          obj.position.z = -center.z * scale;
          
          scene.add(obj);
          
          const sceneObj = {
            id: Date.now(),
            name: filename,
            model: obj,
            visible: true,
            position: obj.position.toArray(),
            rotation: obj.rotation.toArray(),
            scale: obj.scale.toArray()
          };
          
          addSceneObject(sceneObj);
          setHasModels(true);
          
          camera.position.set(5, 5, 5);
          controls.target.set(0, size.y * scale / 2, 0);
          controls.update();
          
          addChatMessage('assistant', `Модель "${filename}" успешно добавлена на сцену!`);
          
          if (onModelLoaded) {
            onModelLoaded();
          }
        },
        (progress) => {
          console.log('Loading progress:', progress);
        },
        (error) => {
          console.error('Error loading model:', error);
          addChatMessage('assistant', `Ошибка загрузки OBJ модели: ${error.message}`);
        }
      );
    } else {
      addChatMessage('assistant', `Формат ${extension.toUpperCase()} пока не поддерживается`);
    }
  };

  return (
    <div className="viewer-panel">
      {!hasModels && (
        <div className="empty-state">
          <div className="empty-state-icon">🎨</div>
          <div>Начните диалог с AI или загрузите 3D модель</div>
        </div>
      )}
      <div ref={containerRef} className="viewer-container" />
      {hasModels && (
        <div className="controls-hint">
          <strong>Управление:</strong>
          Вращение: ЛКМ<br/>
          Перемещение: ПКМ<br/>
          Масштаб: Колесо мыши
        </div>
      )}
    </div>
  );
};

export default ViewerPanel;
