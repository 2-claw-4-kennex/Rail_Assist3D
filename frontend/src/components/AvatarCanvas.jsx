/**
 * RailAssist 3D — React Three Fiber 3D Avatar Scene & Morph Target Animator (Epic 2 & F5)
 * Loads `/models/avatar.glb` (Ready Player Me compatible .glb with `jawOpen`, `mouthSmile`,
 * and `eyeBlink` morph targets) and drives `jawOpen` in real time at 60 FPS using the
 * Web Audio API AnalyserNode amplitude from `sampleJawOpenWeight()`.
 */

import React, { Suspense, useEffect, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { ContactShadows, Float, Html, useGLTF } from '@react-three/drei';
import * as THREE from 'three';
import { KIOSK_STATES } from '../hooks/useKioskStateMachine.js';

const STATE_RING_COLORS = {
  [KIOSK_STATES.IDLE]: '#38bdf8',
  [KIOSK_STATES.LISTENING]: '#22c55e',
  [KIOSK_STATES.PROCESSING]: '#f59e0b',
  [KIOSK_STATES.SPEAKING]: '#818cf8',
  [KIOSK_STATES.ERROR]: '#ef4444',
};

function GLBAvatarMesh({ kioskState, sampleJawOpenWeight }) {
  const { scene } = useGLTF('/models/avatar.glb');
  const avatarGroupRef = useRef();
  const morphMeshesRef = useRef([]);
  const jawFallbackNodeRef = useRef(null);

  useEffect(() => {
    const meshesWithMorphs = [];
    scene.traverse((child) => {
      if (child.isMesh) {
        child.castShadow = true;
        child.receiveShadow = true;
        if (child.morphTargetDictionary && child.morphTargetInfluences) {
          meshesWithMorphs.push(child);
        }
      }
      if (child.name && child.name.toLowerCase().includes('jaw')) {
        jawFallbackNodeRef.current = child;
      }
    });
    morphMeshesRef.current = meshesWithMorphs;
  }, [scene]);

  useFrame((state) => {
    const t = state.clock.getElapsedTime();
    const jawWeight = sampleJawOpenWeight();

    // 1. Update `jawOpen` / `viseme_aa` / `mouthOpen` blendshapes on all morph-capable meshes (F5)
    for (const mesh of morphMeshesRef.current) {
      const dict = mesh.morphTargetDictionary;
      const influences = mesh.morphTargetInfluences;
      if (!dict || !influences) continue;

      const jawIdx =
        dict.jawOpen ?? dict.mouthOpen ?? dict.viseme_aa ?? dict[0];
      if (jawIdx !== undefined && influences[jawIdx] !== undefined) {
        influences[jawIdx] = THREE.MathUtils.lerp(
          influences[jawIdx],
          jawWeight,
          0.45
        );
      }

      const smileIdx = dict.mouthSmile ?? dict.viseme_I;
      if (smileIdx !== undefined && influences[smileIdx] !== undefined) {
        const targetSmile = kioskState === KIOSK_STATES.ERROR ? 0.0 : 0.25;
        influences[smileIdx] = THREE.MathUtils.lerp(
          influences[smileIdx],
          targetSmile,
          0.1
        );
      }

      // Periodic natural eye blink every ~3.8 seconds
      const blinkWave = Math.sin(t * 1.65) > 0.96 ? 1.0 : 0.0;
      const blinkL = dict.eyeBlinkLeft ?? dict.eyesClosed;
      const blinkR = dict.eyeBlinkRight ?? dict.eyesClosed;
      if (blinkL !== undefined && influences[blinkL] !== undefined) {
        influences[blinkL] = THREE.MathUtils.lerp(influences[blinkL], blinkWave, 0.35);
      }
      if (blinkR !== undefined && influences[blinkR] !== undefined) {
        influences[blinkR] = THREE.MathUtils.lerp(influences[blinkR], blinkWave, 0.35);
      }
    }

    // Also drive articulated jaw node if present
    if (jawFallbackNodeRef.current) {
      jawFallbackNodeRef.current.position.y = -0.18 - jawWeight * 0.14;
      jawFallbackNodeRef.current.scale.y = 1.0 + jawWeight * 0.45;
    }

    // 2. Subtle organic head sway & state-reactive posture
    if (avatarGroupRef.current) {
      const listeningLean = kioskState === KIOSK_STATES.LISTENING ? 0.08 : 0.0;
      const speakingNod =
        kioskState === KIOSK_STATES.SPEAKING
          ? Math.sin(t * 9.0) * jawWeight * 0.06
          : 0.0;

      avatarGroupRef.current.rotation.y = Math.sin(t * 0.9) * 0.09;
      avatarGroupRef.current.rotation.x =
        THREE.MathUtils.lerp(
          avatarGroupRef.current.rotation.x,
          listeningLean + speakingNod,
          0.12
        );
    }
  });

  return (
    <group ref={avatarGroupRef} position={[0, -0.35, 0]} scale={1.35}>
      <primitive object={scene} />
    </group>
  );
}

function HolographicStatusRing({ kioskState, sampleJawOpenWeight }) {
  const ringRef = useRef();
  const outerRingRef = useRef();
  const ringColor = STATE_RING_COLORS[kioskState] || '#38bdf8';

  useFrame((state, delta) => {
    const jawWeight = sampleJawOpenWeight();
    if (ringRef.current) {
      ringRef.current.rotation.z +=
        delta * (kioskState === KIOSK_STATES.PROCESSING ? 2.8 : 0.6);
      const pulseScale = 1.0 + jawWeight * 0.18;
      ringRef.current.scale.set(pulseScale, pulseScale, 1);
    }
    if (outerRingRef.current) {
      outerRingRef.current.rotation.z -= delta * 0.4;
    }
  });

  return (
    <group position={[0, 0.15, -0.7]}>
      <mesh ref={ringRef}>
        <torusGeometry args={[1.05, 0.022, 16, 64]} />
        <meshStandardMaterial
          color={ringColor}
          emissive={ringColor}
          emissiveIntensity={1.6}
          transparent
          opacity={0.85}
        />
      </mesh>
      <mesh ref={outerRingRef}>
        <ringGeometry args={[1.18, 1.21, 64]} />
        <meshBasicMaterial
          color={ringColor}
          side={THREE.DoubleSide}
          transparent
          opacity={0.35}
        />
      </mesh>
    </group>
  );
}

export default function AvatarCanvas({ kioskState, sampleJawOpenWeight }) {
  const activeColor = STATE_RING_COLORS[kioskState] || '#38bdf8';

  return (
    <div className="avatar-canvas-container">
      <Canvas
        shadows
        camera={{ position: [0, 0.2, 2.85], fov: 38 }}
        gl={{ antialias: true, powerPreference: 'high-performance' }}
      >
        <color attach="background" args={['#070d19']} />
        <fog attach="fog" args={['#070d19', 4.5, 9.5]} />

        {/* Studio 3-Point Lighting + State-Reactive Rim Light */}
        <ambientLight intensity={0.75} />
        <directionalLight
          position={[2.5, 4.0, 3.5]}
          intensity={1.6}
          castShadow
          shadow-mapSize={[1024, 1024]}
        />
        <pointLight position={[-2.5, 1.5, 2.0]} intensity={0.9} color="#38bdf8" />
        <pointLight position={[0, 1.8, -1.8]} intensity={1.8} color={activeColor} />

        <HolographicStatusRing
          kioskState={kioskState}
          sampleJawOpenWeight={sampleJawOpenWeight}
        />

        <Suspense
          fallback={
            <Html center>
              <div className="canvas-loading-badge">Loading 3D Avatar (.glb)...</div>
            </Html>
          }
        >
          <Float speed={1.6} rotationIntensity={0.04} floatIntensity={0.12}>
            <GLBAvatarMesh
              kioskState={kioskState}
              sampleJawOpenWeight={sampleJawOpenWeight}
            />
          </Float>
        </Suspense>

        <ContactShadows
          position={[0, -1.45, 0]}
          opacity={0.55}
          scale={5}
          blur={2.4}
          far={4}
        />
      </Canvas>
    </div>
  );
}

useGLTF.preload('/models/avatar.glb');
