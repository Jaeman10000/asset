import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { useGLTF, MeshTransmissionMaterial, Environment } from '@react-three/drei';
import * as THREE from 'three';

interface HeartCoreProps {
  /** Path to the GLB exported from Meshy, e.g. '/models/heart.glb' */
  modelPath: string;
  /** Live BPM value driving the pulse animation */
  bpm?: number;
  /** The single "life color" — must match the aurora background + card glow hue */
  attenuationColor?: string;
  scale?: number;
}

/**
 * Anatomical heart core rendered with MeshTransmissionMaterial for a
 * translucent, glowing, "alive" look — replaces the flat 2D heart icon.
 *
 * Everything downstream (aurora background, card border glow) should reuse
 * `attenuationColor` so the whole scene reads as lit by a single source.
 */
export function HeartCore({
  modelPath,
  bpm = 72,
  attenuationColor = '#2be6c8', // teal — matches the reference mood image
  scale = 1,
}: HeartCoreProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const { nodes } = useGLTF(modelPath) as unknown as {
    nodes: Record<string, THREE.Mesh>;
  };

  // Assumes Meshy export has a single main mesh node — adjust the key
  // to match whatever your GLB actually names it (check with
  // `console.log(nodes)` once, or view in an online GLTF viewer).
  //
  // NOTE (JJ): once you know the real node name from the GLB viewer,
  // replace this whole block with the direct, type-safe version:
  //   const heartGeometry = nodes.YourRealMeshName.geometry;
  // The find() below is a temporary fallback and may show a TS warning
  // on `.isMesh` depending on your tsconfig strictness — that's expected.
  const heartGeometry = useMemo(() => {
    const meshNode = Object.values(nodes).find(
      (n): n is THREE.Mesh => (n as THREE.Mesh).isMesh === true
    );
    return meshNode?.geometry;
  }, [nodes]);

  useFrame(({ clock }) => {
    if (!meshRef.current) return;
    const t = clock.getElapsedTime();

    // Real heartbeat is not a clean sine wave: fast systolic contraction,
    // slower diastolic relaxation. Combine two frequencies to fake that
    // asymmetry instead of a single symmetric sin() pulse.
    const beatsPerSecond = bpm / 60;
    const phase = (t * beatsPerSecond) % 1;

    // Sharp contraction spike (first ~30% of cycle), slow decay after.
    const systole = Math.exp(-Math.pow((phase - 0.08) / 0.06, 2)); // sharp beat
    const secondaryBeat = 0.4 * Math.exp(-Math.pow((phase - 0.28) / 0.08, 2)); // dicrotic notch echo

    const pulse = 1 + 0.06 * (systole + secondaryBeat);
    meshRef.current.scale.setScalar(scale * pulse);

    // Very slow idle rotation so the heart never looks perfectly static.
    meshRef.current.rotation.y = Math.sin(t * 0.15) * 0.15;
  });

  if (!heartGeometry) return null;

  return (
    <>
      {/* Required for MeshTransmissionMaterial to look believable —
          without an environment map, transmission reads as flat gray. */}
      <Environment preset="night" />

      <mesh ref={meshRef} geometry={heartGeometry} castShadow>
        <MeshTransmissionMaterial
          transmission={1}
          thickness={2.2}
          roughness={0.08}
          ior={1.4}
          chromaticAberration={0.03}
          anisotropy={0.1}
          distortion={0.15}
          distortionScale={0.3}
          temporalDistortion={0.1}
          attenuationColor={attenuationColor}
          attenuationDistance={0.9}
          color={attenuationColor}
          backside
        />
      </mesh>

      {/* Soft point light from inside the heart — this is what actually
          "washes" the surrounding cards/fog in the reference image.
          Reuse attenuationColor here too. */}
      <pointLight
        position={[0, 0, 0]}
        color={attenuationColor}
        intensity={3}
        distance={8}
        decay={2}
      />
    </>
  );
}

useGLTF.preload; // call useGLTF.preload('/models/heart.glb') at app init if desired
