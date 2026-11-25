import React, { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { ContactShadows, Environment, OrbitControls, useAnimations, useGLTF } from "@react-three/drei";

function pickAction(actions, target) {
  const names = Object.keys(actions);
  if (!names.length) return null;

  const findBy = (patterns) =>
    names.find((n) => patterns.some((p) => n.toLowerCase().includes(p)));

  let match = null;
  if (target === "dance") {
    match = findBy(["dance", "hiphop", "salsa"]);
  } else if (target === "talkHands") {
    match = findBy(["hand", "gesture", "talk2", "talking_hands", "explain"]);
  } else if (target === "talk") {
    match = findBy(["talk", "speak"]);
  } else {
    match = findBy(["idle", "stand", "breath"]);
  }

  return actions[match || names[0]];
}

function LoadedAvatar({ url, animation }) {
  const group = useRef();
  const { scene, animations } = useGLTF(url);
  const { actions } = useAnimations(animations, group);

  useEffect(() => {
    const next = pickAction(actions, animation);
    if (!next) return;
    Object.values(actions).forEach((a) => {
      if (a && a !== next) a.fadeOut(0.35);
    });
    next.reset().fadeIn(0.35).play();
    return () => next.fadeOut(0.35);
  }, [animation, actions]);

  return <primitive ref={group} object={scene} position={[0, -1.45, 0]} scale={1.15} />;
}

function FallbackAvatar({ animation }) {
  const ref = useRef();

  useFrame(({ clock }) => {
    if (!ref.current) return;
    const t = clock.getElapsedTime();
    if (animation === "dance") {
      ref.current.rotation.y = Math.sin(t * 5) * 0.45;
      ref.current.position.y = Math.abs(Math.sin(t * 6)) * 0.18;
    } else if (animation === "talk" || animation === "talkHands") {
      ref.current.rotation.y = Math.sin(t * 2.5) * 0.12;
      ref.current.position.y = Math.sin(t * 4) * 0.03;
    } else {
      ref.current.rotation.y = Math.sin(t * 0.8) * 0.05;
      ref.current.position.y = Math.sin(t * 1.5) * 0.02;
    }
  });

  return (
    <group ref={ref} position={[0, -0.1, 0]}>
      <mesh position={[0, 0.45, 0]}>
        <sphereGeometry args={[0.32, 32, 32]} />
        <meshStandardMaterial color="#1f2937" roughness={0.35} />
      </mesh>
      <mesh position={[0, -0.25, 0]}>
        <capsuleGeometry args={[0.3, 0.55, 16, 32]} />
        <meshStandardMaterial color="#0f4c81" roughness={0.4} />
      </mesh>
    </group>
  );
}

export default function AvatarCanvas({ animation, appState }) {
  const [hasModel, setHasModel] = useState(false);
  const modelUrl = useMemo(() => "/models/avatar.glb", []);

  useEffect(() => {
    fetch(modelUrl, { method: "HEAD" })
      .then((res) => {
        const type = res.headers.get("content-type") || "";
        setHasModel(res.ok && !type.includes("text/html"));
      })
      .catch(() => setHasModel(false));
  }, [modelUrl]);

  return (
    <div className="avatar-stage">
      <div className={`state-pill state-${appState}`}>{appState.toUpperCase()}</div>
      {!hasModel && (
        <div className="model-hint">
          Drop your rigged GLB at <code>frontend/public/models/avatar.glb</code>
        </div>
      )}
      <Canvas camera={{ position: [0, 0.35, 2.2], fov: 36 }} shadows>
        <color attach="background" args={["#F6F1D8"]} />
        <ambientLight intensity={0.8} />
        <directionalLight position={[2.5, 4, 3]} intensity={1.4} castShadow />
        <directionalLight position={[-2, 2, -2]} intensity={0.5} />
        <Suspense fallback={<FallbackAvatar animation={animation} />}>
          {hasModel ? (
            <LoadedAvatar url={modelUrl} animation={animation} />
          ) : (
            <FallbackAvatar animation={animation} />
          )}
          <Environment preset="studio" />
        </Suspense>
        <ContactShadows position={[0, -1.45, 0]} opacity={0.35} scale={5} blur={2.4} />
        <OrbitControls target={[0, 0.15, 0]} enablePan={false} minDistance={1.5} maxDistance={3.2} />
      </Canvas>
    </div>
  );
}
