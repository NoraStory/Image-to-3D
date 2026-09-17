/*
 * Minimal in-browser OBJ viewer used by the web UI.
 * The GLB/USDZ preview path uses <model-viewer>; OBJ is rendered here with
 * three.js so that every supported output format can be previewed directly.
 */
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js';
import { OBJLoader } from 'https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/loaders/OBJLoader.js';
import { OrbitControls } from 'https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/controls/OrbitControls.js';

let state = null;

function disposeState() {
    if (!state) return;
    cancelAnimationFrame(state.raf);
    state.resizeObserver.disconnect();
    state.controls.dispose();
    state.scene.traverse(obj => {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) {
            const materials = Array.isArray(obj.material) ? obj.material : [obj.material];
            materials.forEach(material => material.dispose());
        }
    });
    state.renderer.dispose();
    if (state.renderer.domElement.parentNode) {
        state.renderer.domElement.parentNode.removeChild(state.renderer.domElement);
    }
    state = null;
}

function fitObject(object) {
    const box = new THREE.Box3().setFromObject(object);
    const size = box.getSize(new THREE.Vector3()).length() || 1;
    const center = box.getCenter(new THREE.Vector3());
    object.position.sub(center);
    const scale = 3 / size;
    object.scale.setScalar(scale);
}

async function init(container, url) {
    disposeState();

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b0e14);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    container.appendChild(renderer.domElement);

    const camera = new THREE.PerspectiveCamera(50, 1, 0.01, 100);
    camera.position.set(3, 1.8, 4);

    scene.add(new THREE.HemisphereLight(0xffffff, 0x334155, 1.6));
    const keyLight = new THREE.DirectionalLight(0xffffff, 1.4);
    keyLight.position.set(4, 6, 5);
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0x38bdf8, 0.7);
    fillLight.position.set(-4, -2, -3);
    scene.add(fillLight);

    const grid = new THREE.GridHelper(6, 20, 0x334155, 0x1e293b);
    scene.add(grid);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 0.8;
    controls.maxDistance = 12;

    const resize = () => {
        const width = Math.max(container.clientWidth, 1);
        const height = Math.max(container.clientHeight, 1);
        renderer.setSize(width, height, false);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
    };
    resize();

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);

    const animate = () => {
        state.raf = requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
    };

    state = { renderer, scene, camera, controls, resizeObserver, raf: 0 };

    try {
        const object = await new OBJLoader().loadAsync(url);
        object.traverse(child => {
            if (child.isMesh) {
                child.material = new THREE.MeshNormalMaterial({ flatShading: false });
            }
        });
        fitObject(object);
        scene.add(object);
        document.getElementById('viewerLoading').style.display = 'none';
    } catch (err) {
        disposeState();
        throw err;
    }

    animate();
}

function dispose() {
    disposeState();
}

window.ObjViewer = { init, dispose };
