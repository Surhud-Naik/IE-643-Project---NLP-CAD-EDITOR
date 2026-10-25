import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RotateCcw, Eye } from 'lucide-react';

interface ThreeViewerProps {
  title: string;
  stlUrl?: string;
  glbUrl?: string;
  overlayGlbUrl?: string;
  isOverlayMode?: boolean;
  color?: string;
  wireframeDefault?: boolean;
  onCameraChange?: (cam: { position: THREE.Vector3; target: THREE.Vector3 }) => void;
  externalCameraState?: { position: THREE.Vector3; target: THREE.Vector3 } | null;
  height?: string;
}

export const ThreeViewer: React.FC<ThreeViewerProps> = ({
  title,
  stlUrl,
  glbUrl,
  overlayGlbUrl,
  isOverlayMode = false,
  color = '#0ea5e9',
  wireframeDefault = false,
  onCameraChange,
  externalCameraState,
  height = '380px'
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const [wireframe, setWireframe] = useState(wireframeDefault);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const modelGroupRef = useRef<THREE.Group | null>(null);
  const overlayGroupRef = useRef<THREE.Group | null>(null);

  // Initialize Three.js scene
  useEffect(() => {
    if (!mountRef.current) return;
    const container = mountRef.current;
    const width = container.clientWidth || 400;
    const heightPx = parseInt(height, 10) || 380;

    // 1. Scene & Camera
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0c1322);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(45, width / heightPx, 0.1, 1000);
    camera.position.set(50, 50, 50);
    cameraRef.current = camera;

    // 2. Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, heightPx);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    container.innerHTML = '';
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // 3. Orbit Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.maxDistance = 600;
    controls.minDistance = 5;
    controlsRef.current = controls;

    if (onCameraChange) {
      controls.addEventListener('change', () => {
        onCameraChange({
          position: camera.position.clone(),
          target: controls.target.clone()
        });
      });
    }

    // 4. Studio Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 1.2);
    dirLight1.position.set(60, 100, 70);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x38bdf8, 0.6);
    dirLight2.position.set(-50, -30, -50);
    scene.add(dirLight2);

    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x1e293b, 0.5);
    scene.add(hemiLight);

    // 5. Grid helper
    const grid = new THREE.GridHelper(120, 24, 0x334155, 0x1e293b);
    grid.position.y = -0.1;
    scene.add(grid);

    // Groups for models
    const modelGroup = new THREE.Group();
    scene.add(modelGroup);
    modelGroupRef.current = modelGroup;

    const overlayGroup = new THREE.Group();
    scene.add(overlayGroup);
    overlayGroupRef.current = overlayGroup;

    // Animation Loop
    let animId: number;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // Resize Handler
    const handleResize = () => {
      if (!mountRef.current || !rendererRef.current || !cameraRef.current) return;
      const newW = mountRef.current.clientWidth;
      const newH = parseInt(height, 10) || 380;
      cameraRef.current.aspect = newW / newH;
      cameraRef.current.updateProjectionMatrix();
      rendererRef.current.setSize(newW, newH);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', handleResize);
      renderer.dispose();
      container.innerHTML = '';
    };
  }, [height]);

  // Sync with external camera state if linked
  useEffect(() => {
    if (!externalCameraState || !cameraRef.current || !controlsRef.current) return;
    cameraRef.current.position.copy(externalCameraState.position);
    controlsRef.current.target.copy(externalCameraState.target);
    controlsRef.current.update();
  }, [externalCameraState]);

  // Load Primary Model (STL or GLB)
  useEffect(() => {
    if (!modelGroupRef.current || !sceneRef.current) return;
    const group = modelGroupRef.current;
    // Clear previous children
    while (group.children.length > 0) {
      group.remove(group.children[0]);
    }

    if (!stlUrl && !glbUrl) {
      return;
    }

    setLoading(true);
    setError(null);

    const fitCameraToObject = (object: THREE.Object3D) => {
      const box = new THREE.Box3().setFromObject(object);
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());
      const maxDim = Math.max(size.x, size.y, size.z);
      const fov = cameraRef.current?.fov || 45;
      const cameraDist = (maxDim / 2) / Math.tan((Math.PI * fov) / 360) * 1.8;

      if (cameraRef.current && controlsRef.current) {
        cameraRef.current.position.set(center.x + cameraDist * 0.7, center.y + cameraDist * 0.7, center.z + cameraDist * 0.7);
        controlsRef.current.target.copy(center);
        controlsRef.current.update();
      }
    };

    if (glbUrl) {
      const loader = new GLTFLoader();
      loader.load(
        glbUrl,
        (gltf) => {
          const root = gltf.scene;
          root.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
              const mesh = child as THREE.Mesh;
              mesh.material = new THREE.MeshStandardMaterial({
                color: isOverlayMode ? 0x06b6d4 : new THREE.Color(color),
                roughness: 0.35,
                metalness: 0.25,
                wireframe: wireframe
              });
              mesh.castShadow = true;
              mesh.receiveShadow = true;
            }
          });
          group.add(root);
          fitCameraToObject(root);
          setLoading(false);
        },
        undefined,
        (err) => {
          console.warn('GLB load error, trying STL fallback if available', err);
          if (!stlUrl) {
            setError('Failed to load 3D GLB model.');
            setLoading(false);
          }
        }
      );
    } else if (stlUrl) {
      const stlLoader = new STLLoader();
      stlLoader.load(
        stlUrl,
        (geom) => {
          geom.computeVertexNormals();
          const mat = new THREE.MeshStandardMaterial({
            color: isOverlayMode ? 0x06b6d4 : new THREE.Color(color),
            roughness: 0.35,
            metalness: 0.25,
            wireframe: wireframe
          });
          const mesh = new THREE.Mesh(geom, mat);
          mesh.castShadow = true;
          mesh.receiveShadow = true;
          group.add(mesh);
          fitCameraToObject(mesh);
          setLoading(false);
        },
        undefined,
        () => {
          setError('Failed to load 3D STL mesh.');
          setLoading(false);
        }
      );
    }
  }, [stlUrl, glbUrl, color, wireframe, isOverlayMode]);

  // Load Overlay Ghost Model (Original in translucent grey when in overlay mode)
  useEffect(() => {
    if (!overlayGroupRef.current) return;
    const group = overlayGroupRef.current;
    while (group.children.length > 0) {
      group.remove(group.children[0]);
    }

    if (!isOverlayMode || !overlayGlbUrl) return;

    const loader = new GLTFLoader();
    loader.load(overlayGlbUrl, (gltf) => {
      const ghost = gltf.scene;
      ghost.traverse((child) => {
        if ((child as THREE.Mesh).isMesh) {
          const mesh = child as THREE.Mesh;
          mesh.material = new THREE.MeshStandardMaterial({
            color: 0x94a3b8, // Slate grey ghost
            transparent: true,
            opacity: 0.35,
            roughness: 0.8,
            metalness: 0.1,
            wireframe: false
          });
        }
      });
      group.add(ghost);
    });
  }, [isOverlayMode, overlayGlbUrl]);

  // Toggle wireframe on active mesh
  const toggleWireframe = () => {
    setWireframe((prev) => !prev);
    if (modelGroupRef.current) {
      modelGroupRef.current.traverse((child) => {
        if ((child as THREE.Mesh).isMesh) {
          const m = child as THREE.Mesh;
          if (Array.isArray(m.material)) {
            m.material.forEach((mat: any) => { if (mat) mat.wireframe = !wireframe; });
          } else if (m.material) {
            (m.material as any).wireframe = !wireframe;
          }
        }
      });
    }
  };

  // Reset camera view
  const resetCamera = () => {
    if (modelGroupRef.current && modelGroupRef.current.children.length > 0) {
      const box = new THREE.Box3().setFromObject(modelGroupRef.current);
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());
      const maxDim = Math.max(size.x, size.y, size.z);
      const dist = (maxDim / 2) / Math.tan((Math.PI * 45) / 360) * 1.8;

      if (cameraRef.current && controlsRef.current) {
        cameraRef.current.position.set(center.x + dist * 0.7, center.y + dist * 0.7, center.z + dist * 0.7);
        controlsRef.current.target.copy(center);
        controlsRef.current.update();
      }
    }
  };

  return (
    <div className="glass-card" style={{ position: 'relative', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {/* Header Bar */}
      <div style={{
        padding: '0.65rem 1rem',
        borderBottom: '1px solid var(--border-color)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'rgba(15, 23, 42, 0.4)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: color }} />
          <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>{title}</span>
          {isOverlayMode && (
            <span className="badge badge-cyan" style={{ fontSize: '0.65rem', padding: '0.1rem 0.4rem' }}>
              Ghost Overlay
            </span>
          )}
        </div>

        {/* View Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <button
            onClick={toggleWireframe}
            className="btn-outline"
            title="Toggle Wireframe / Shaded"
            style={{ padding: '0.3rem 0.5rem' }}
          >
            <Eye size={14} />
            <span style={{ fontSize: '0.75rem' }}>{wireframe ? 'Shaded' : 'Wire'}</span>
          </button>
          <button
            onClick={resetCamera}
            className="btn-outline"
            title="Reset Camera View"
            style={{ padding: '0.3rem 0.5rem' }}
          >
            <RotateCcw size={14} />
          </button>
        </div>
      </div>

      {/* Canvas Mount Container */}
      <div
        style={{
          width: '100%',
          height: height,
          position: 'relative',
          background: 'radial-gradient(circle at center, #111a2e 0%, #080d1a 100%)',
          overflow: 'hidden'
        }}
      >
        {/* Dedicated Three.js canvas mount point */}
        <div ref={mountRef} style={{ width: '100%', height: '100%', position: 'absolute', inset: 0 }} />

        {loading && (
          <div style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(12, 19, 34, 0.7)',
            zIndex: 10
          }}>
            <div className="animate-spin" style={{
              width: '28px',
              height: '28px',
              border: '3px solid rgba(14, 165, 233, 0.2)',
              borderTopColor: 'var(--accent-blue)',
              borderRadius: '50%'
            }} />
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
              Tessellating 3D solid...
            </span>
          </div>
        )}

        {error && (
          <div style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--accent-rose)',
            fontSize: '0.85rem',
            padding: '1rem',
            textAlign: 'center'
          }}>
            {error}
          </div>
        )}

        {!loading && !error && !stlUrl && !glbUrl && (
          <div style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-faint)',
            fontSize: '0.85rem'
          }}>
            Execute or load a model to render 3D geometry
          </div>
        )}
      </div>
    </div>
  );
};
