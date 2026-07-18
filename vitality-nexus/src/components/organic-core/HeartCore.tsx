import { Component, Suspense, useEffect, useMemo, useRef, type ReactNode } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { useGLTF, MeshTransmissionMaterial } from '@react-three/drei';
import * as THREE from 'three';
import { createPlaceholderHeartGeometry } from './placeholderHeart';

interface HeartCoreProps {
  /** Path to the GLB exported from Meshy, e.g. '/models/heart.glb' */
  modelPath: string;
  /** Live BPM value driving the pulse animation */
  bpm?: number;
  /** The single "life color" — must match the aurora background + card glow hue */
  attenuationColor?: string;
  scale?: number;
  /**
   * 트랜스미션 버퍼 해상도. drei 기본값(풀스크린×dpr)은 backside와 결합하면
   * 매 프레임 풀해상도 씬 2회 추가 렌더 = 이 씬의 지배적 비용이 된다.
   * 유리 굴절 특성상 1024로 낮춰도 시각 차이가 거의 없다.
   */
  transmissionRes?: number;
  /**
   * backside=true면 뒷면 굴절까지 계산해 더 사실적이지만 매 프레임 씬을 한 번 더
   * 렌더한다(2배 비용). 약한 GPU에서는 false로 두면 렉이 크게 준다 (앞면 굴절만).
   */
  backside?: boolean;
}

interface HeartMeshProps {
  bpm: number;
  attenuationColor: string;
  scale: number;
  transmissionRes: number;
  backside: boolean;
}

/**
 * Anatomical heart core rendered with MeshTransmissionMaterial for a
 * translucent, glowing, "alive" look — replaces the flat 2D heart icon.
 *
 * Everything downstream (aurora background, card border glow) should reuse
 * `attenuationColor` so the whole scene reads as lit by a single source.
 *
 * GLB(`modelPath`)가 없거나 로드에 실패하면 절차적 폴백 심장(placeholderHeart)을
 * 자동으로 사용한다. Meshy에서 만든 heart.glb를 public/models/에 넣으면
 * 코드 수정 없이 GLB로 전환된다 (로드 실패가 캐시되므로 새로고침 필요).
 */
export function HeartCore({
  modelPath,
  bpm = 72,
  attenuationColor = '#2be6c8', // teal — matches the reference mood image
  scale = 1,
  transmissionRes = 512,
  backside = true,
}: HeartCoreProps) {
  const meshProps: HeartMeshProps = { bpm, attenuationColor, scale, transmissionRes, backside };

  return (
    <>
      {/* Required for MeshTransmissionMaterial to look believable —
          without an environment map, transmission reads as flat gray.
          기본은 절차적 "나이트 스튜디오"(아래 buildNightStudioEnv) — 검은 공간에
          라이트 스트립만 있어 유리에 줄무늬 하이라이트만 남는다. drei 프리셋(풍경
          노출)·RoomEnvironment(과노출)는 무드를 깨서 쓰지 않는다.
          Poly Haven HDR로 교체하려면 drei에서 Environment를 다시 import한 뒤:
            <Environment files="/env/studio_small_04.hdr" /> */}
      <ProceduralEnvironment washColor={attenuationColor} />

      {/* 홀로그램 후광 — Bloom을 껐으므로(트랜스미션 피드백/렉 방지) 심장 뒤에
          가산 발광 스프라이트로 부드러운 halo를 직접 낸다. 값이 고정이라
          시간이 지나도 쌓이지 않는다 (Bloom 같은 폭주 없음). */}
      <HeartGlow color={attenuationColor} bpm={bpm} scale={scale} />

      <SafeMount
        fallback={<PlaceholderHeart {...meshProps} />}
        onError={() =>
          console.warn(
            '[HeartCore] heart.glb 로드 실패 — 절차적 폴백 심장 사용. ' +
              'GLB가 없으면: Meshy GLB를 public/models/heart.glb에 넣고 새로고침. ' +
              'GLB가 있는데도 실패하면: Draco 압축 여부/네트워크(디코더 CDN)를 확인.'
          )
        }
      >
        <Suspense fallback={<PlaceholderHeart {...meshProps} />}>
          <GLBHeart modelPath={modelPath} {...meshProps} />
        </Suspense>
      </SafeMount>

      {/* Soft point light from inside the heart — this is what actually
          "washes" the surrounding cards/fog in the reference image.
          Reuse attenuationColor here too.
          three 물리 단위(candela) 기준 보정: 3은 안 보이고 18은 유리 내면
          스페큘러가 과노출→흰색으로 날아간다. */}
      <pointLight
        position={[0, 0, 0]}
        color={attenuationColor}
        intensity={3.2}
        distance={8}
        decay={2}
      />
    </>
  );
}

/** Meshy GLB에서 첫 번째 mesh 노드를 찾아 심장으로 렌더 */
function GLBHeart({ modelPath, ...meshProps }: HeartMeshProps & { modelPath: string }) {
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
  const heartGeometry = useMemo(() => {
    const meshNode = Object.values(nodes).find(
      (n): n is THREE.Mesh => (n as THREE.Mesh).isMesh === true
    );
    return meshNode?.geometry;
  }, [nodes]);

  if (!heartGeometry) return <PlaceholderHeart {...meshProps} />;
  return <HeartMesh geometry={heartGeometry} {...meshProps} />;
}

/**
 * HeartGlow — 심장 뒤 홀로그램 후광 (가산 발광 스프라이트).
 * Bloom을 껐으므로(트랜스미션 피드백/렉 방지) 이걸로 halo를 낸다. 값이 고정이라
 * 프레임을 거듭해도 밝기가 쌓이지 않는다. 심박에 맞춰 아주 약하게 숨쉰다(스케일).
 */
function HeartGlow({ color, bpm, scale }: { color: string; bpm: number; scale: number }) {
  const spriteRef = useRef<THREE.Sprite>(null);
  const tex = useMemo(() => {
    const c = document.createElement('canvas');
    c.width = c.height = 128;
    const ctx = c.getContext('2d')!;
    const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
    // 아주 부드러운 확산 — 딱딱한 코어 없이 심장 주위로 은은하게 번지게
    g.addColorStop(0, 'rgba(220,255,248,0.5)');
    g.addColorStop(0.3, 'rgba(120,240,220,0.24)');
    g.addColorStop(0.65, 'rgba(43,230,200,0.09)');
    g.addColorStop(1, 'rgba(43,230,200,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 128, 128);
    return new THREE.CanvasTexture(c);
  }, []);
  useEffect(() => () => tex.dispose(), [tex]);

  useFrame(({ clock }) => {
    if (!spriteRef.current) return;
    const t = clock.getElapsedTime();
    const phase = ((t * bpm) / 60) % 1;
    const beat = Math.exp(-Math.pow((phase - 0.08) / 0.07, 2)); // 심박과 같은 위상
    const s = scale * (7 + 0.6 * beat); // halo는 심장보다 크고 넓게(은은한 대기감)
    spriteRef.current.scale.set(s, s, 1);
  });

  return (
    <sprite ref={spriteRef} position={[0, 0, -0.2]}>
      <spriteMaterial
        map={tex}
        color={color}
        transparent
        opacity={0.3}
        depthWrite={false}
        depthTest={false}
        blending={THREE.AdditiveBlending}
      />
    </sprite>
  );
}

/** GLB가 없을 때 쓰는 절차적 심장 */
function PlaceholderHeart(props: HeartMeshProps) {
  const geometry = useMemo(() => createPlaceholderHeartGeometry(), []);
  // prop으로 주입한 지오메트리는 R3F가 자동 dispose하지 않음 — 직접 정리
  useEffect(() => () => geometry.dispose(), [geometry]);
  return <HeartMesh geometry={geometry} {...props} />;
}

/** 심박 애니메이션 + 유리질 트랜스미션 재질 (GLB/폴백 공용) */
function HeartMesh({
  geometry,
  bpm,
  attenuationColor,
  scale,
  transmissionRes,
  backside,
}: HeartMeshProps & { geometry: THREE.BufferGeometry }) {
  const meshRef = useRef<THREE.Mesh>(null);

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

  return (
    <mesh ref={meshRef} geometry={geometry} castShadow>
      <MeshTransmissionMaterial
        transmission={1}
        thickness={2.2}
        roughness={0.14}
        ior={1.4}
        chromaticAberration={0.03}
        anisotropy={0.1}
        // 트랜스미션 패스 해상도 명시 — 미지정 시 풀스크린×dpr 렌더타깃 2개가
        // 생겨 매 프레임 씬을 2회 추가 렌더하는 것이 지배 비용이 된다
        resolution={transmissionRes}
        backsideResolution={Math.max(256, transmissionRes / 2)}
        // 오로라 배경을 제거했으므로 굴절 왜곡은 약하게 (성능 + 깔끔함)
        distortion={0.15}
        distortionScale={0.3}
        temporalDistortion={0}
        attenuationColor={attenuationColor}
        // 0.9는 두께 전체가 청록으로 포화되어 평평해 보임 — 가장자리만 물들게
        attenuationDistance={1.6}
        color={attenuationColor}
        // 나이트 스튜디오 환경은 원래 어두워서 줄무늬 하이라이트만 남는다 —
        // 여기서 더 줄이면 유리가 죽고, 올리면 은색으로 뜬다
        envMapIntensity={0.72}
        // 생체발광 씨앗: 은은한 내부 발광 (Bloom을 껐으므로 피드백 폭주 없음 —
        // 예전보다 조금 올려 유리 심장에 생기를 준다)
        emissive={attenuationColor}
        emissiveIntensity={0.045}
        backside={backside}
      />
    </mesh>
  );
}

/**
 * 나이트 스튜디오 환경맵 (네트워크 불필요, 절차적).
 *
 * "검은 공간 + 라이트 스트립"을 직접 구성해 PMREM으로 굽는다.
 * → 유리에는 가느다란 하이라이트 줄무늬만 생기고 몸체는 어둡게 유지되어
 *   심장 내부의 청록빛(단일 광원)이 주인공이 된다.
 *
 * washColor: 뒤쪽 스트립의 색 — 색 단일 소스(lifeColors.LIFE_COLOR)에서 내려오는
 * attenuationColor를 그대로 받아, 유리 환경 반사까지 같은 생명색을 공유한다.
 */
function buildNightStudioEnv(washColor: string): THREE.Scene {
  const env = new THREE.Scene();

  const addStrip = (
    color: string,
    intensity: number,
    size: [number, number],
    pos: [number, number, number]
  ) => {
    const mat = new THREE.MeshBasicMaterial({
      color: new THREE.Color(color).multiplyScalar(intensity),
      side: THREE.DoubleSide,
    });
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(...size), mat);
    mesh.position.set(...pos);
    mesh.lookAt(0, 0, 0);
    env.add(mesh);
  };

  addStrip('#ffffff', 5, [3, 0.5], [2.5, 3, 2]); // 키 스트립 (우상단 긴 줄무늬)
  addStrip('#ffffff', 2.5, [0.4, 2.5], [-3, 0.8, 1.6]); // 림 스트립 (좌측 세로)
  addStrip(washColor, 1.5, [4, 2], [0, -0.5, -4]); // 생명색 워시 (뒤쪽 반사)

  return env;
}

function ProceduralEnvironment({ washColor }: { washColor: string }) {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);

  useEffect(() => {
    const pmrem = new THREE.PMREMGenerator(gl);
    const envScene = buildNightStudioEnv(washColor);
    const envTex = pmrem.fromScene(envScene, 0.08).texture;
    scene.environment = envTex;

    // 베이크용 임시 씬의 GPU 리소스는 three가 강참조로 보관하므로 직접 dispose
    envScene.traverse((obj) => {
      if (obj instanceof THREE.Mesh) {
        obj.geometry.dispose();
        (obj.material as THREE.Material).dispose();
      }
    });

    return () => {
      scene.environment = null;
      envTex.dispose();
      pmrem.dispose();
    };
  }, [gl, scene, washColor]);

  return null;
}

/** Suspense 하위에서 로더 실패를 잡아 폴백으로 전환하는 에러 경계 */
class SafeMount extends Component<
  { fallback?: ReactNode; onError?: (error: unknown) => void; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    this.props.onError?.(error);
  }

  render() {
    return this.state.failed ? (this.props.fallback ?? null) : this.props.children;
  }
}
