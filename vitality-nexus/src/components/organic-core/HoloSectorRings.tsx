import { useEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

/**
 * HoloSectorRings — 심장 주위를 도는 홀로그램 섹터 궤도.
 *
 * 2D 캔버스 오브가 3D 심장과 질감이 안 맞아 몰입을 깨던 것을, 심장과 같은
 * R3F 씬 안(같은 조명·Bloom)에서 그려 "의료 홀로그램" 느낌으로 통일한다.
 *   - 안쪽 링 = 한국(KRX) 12섹터, 바깥 링 = 미국(SPDR) 11섹터
 *   - 노드 색 = 정보 인코딩 (KR: 지배 투자자 — 외국인 금/기관 청록/개인 회청,
 *     US: 상승 시안/하락 보라), 노드 크기 = 강도
 *   - 파티클이 심장에서 각 섹터로 흘러나감 (심장 = 파장의 원천)
 *   - 심장 아래 홀로그램 프로젝터 디스크
 * 라벨은 캔버스 텍스처 스프라이트 — 폰트 CDN 불필요(오프라인 Tauri 안전).
 */

export interface RingSector {
  name: string;
  ret: number;
  /** KR만: 투자자별 순매수 강도 0~1 */
  foreign?: number;
  inst?: number;
  individual?: number;
}

const INV_HUES = { foreign: 45, inst: 175, individual: 220 } as const;

/** 섹터의 정보 인코딩 hue (Dashboard 리드아웃과 공유) */
export function sectorHue(s: RingSector, side: 'kr' | 'us'): number {
  if (side === 'kr') {
    const f = s.foreign ?? 0;
    const i = s.inst ?? 0;
    const p = s.individual ?? 0;
    const m = Math.max(f, i, p);
    if (m > 0.05) return m === f ? INV_HUES.foreign : m === i ? INV_HUES.inst : INV_HUES.individual;
    return 175;
  }
  return s.ret >= 0 ? 195 : 240;
}

/**
 * 수급 점수 0~1 — 노드 크기·밝기·파티클 속도를 결정한다.
 * KR: (외국인+기관) 순매수 강도 = 스마트머니 유입 (App에서 정렬한 기준과 동일).
 * US: |등락률| 정규화.
 */
function flowScore(s: RingSector, side: 'kr' | 'us', maxRet: number): number {
  if (side === 'kr') return Math.min(((s.foreign ?? 0) + (s.inst ?? 0)) / 1.6, 1);
  return Math.min(Math.abs(s.ret) / (maxRet || 1), 1);
}

function makeLabelTexture(text: string): THREE.CanvasTexture {
  const c = document.createElement('canvas');
  c.width = 128;
  c.height = 32;
  const ctx = c.getContext('2d')!;
  ctx.font = '600 17px "Segoe UI", "Malgun Gothic", sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.shadowColor = 'rgba(0,0,0,0.9)';
  ctx.shadowBlur = 5;
  ctx.fillStyle = 'rgba(230,240,240,0.92)';
  ctx.fillText(text, 64, 17);
  const tex = new THREE.CanvasTexture(c);
  tex.anisotropy = 2;
  return tex;
}

function makeGlowTexture(): THREE.CanvasTexture {
  const c = document.createElement('canvas');
  c.width = c.height = 64;
  const ctx = c.getContext('2d')!;
  const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, 'rgba(255,255,255,1)');
  g.addColorStop(0.35, 'rgba(255,255,255,0.5)');
  g.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}

function Ring({
  sectors,
  side,
  radius,
  tiltX,
  tiltZ,
  speed,
  glowTex,
}: {
  sectors: RingSector[];
  side: 'kr' | 'us';
  radius: number;
  tiltX: number;
  tiltZ: number;
  speed: number;
  glowTex: THREE.Texture;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const pointsRef = useRef<THREE.Points>(null);

  const maxRet = useMemo(
    () => Math.max(...sectors.map((s) => Math.abs(s.ret)), 0.1),
    [sectors],
  );

  // 노드 위치/색/강도 + 라벨 텍스처.
  // sectors는 이미 수급 순으로 정렬돼 들어온다 → i=0(12시)부터 시계방향으로 1위→꼴찌.
  const nodes = useMemo(() => {
    const n = Math.max(sectors.length, 1);
    return sectors.map((s, i) => {
      const angle = -Math.PI / 2 + (i / n) * Math.PI * 2;
      const hue = sectorHue(s, side);
      const score = flowScore(s, side, maxRet);
      return {
        name: s.name,
        rank: i + 1,
        pos: new THREE.Vector3(Math.cos(angle) * radius, 0, Math.sin(angle) * radius),
        color: new THREE.Color(`hsl(${hue}, 88%, 66%)`),
        score,
        label: makeLabelTexture(s.name),
      };
    });
  }, [sectors, side, radius, maxRet]);

  // 라벨 텍스처 정리 (nodes가 바뀔 때/언마운트 시)
  useEffect(() => {
    return () => nodes.forEach((n) => n.label.dispose());
  }, [nodes]);

  // 궤도 선 (원)
  const ringGeo = useMemo(() => {
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i <= 96; i++) {
      const a = (i / 96) * Math.PI * 2;
      pts.push(new THREE.Vector3(Math.cos(a) * radius, 0, Math.sin(a) * radius));
    }
    const g = new THREE.BufferGeometry().setFromPoints(pts);
    return g;
  }, [radius]);
  useEffect(() => () => ringGeo.dispose(), [ringGeo]);

  // 파티클 (심장 중심 → 각 노드, 강도∝속도·밝기)
  const particle = useMemo(() => {
    const n = nodes.length;
    const positions = new Float32Array(n * 3);
    const colors = new Float32Array(n * 3);
    const progress = new Float32Array(n);
    const speeds = new Float32Array(n);
    nodes.forEach((node, i) => {
      // Math.random 대신 노드별 결정적 위상 (시작점만 흩뿌림)
      progress[i] = (i * 0.618) % 1;
      speeds[i] = 0.1 + node.score * 0.45; // 수급 강할수록 빠르게 흐름
      colors[i * 3] = node.color.r;
      colors[i * 3 + 1] = node.color.g;
      colors[i * 3 + 2] = node.color.b;
    });
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    return { geo, progress, speeds };
  }, [nodes]);
  useEffect(() => () => particle.geo.dispose(), [particle]);

  useFrame((_, delta) => {
    if (groupRef.current) groupRef.current.rotation.y += speed * delta;
    // 파티클 진행
    const posAttr = particle.geo.attributes.position as THREE.BufferAttribute;
    const arr = posAttr.array as Float32Array;
    for (let i = 0; i < nodes.length; i++) {
      particle.progress[i] += particle.speeds[i] * delta;
      if (particle.progress[i] > 1) particle.progress[i] -= 1;
      const t = particle.progress[i];
      const n = nodes[i];
      arr[i * 3] = n.pos.x * t;
      arr[i * 3 + 1] = n.pos.y * t;
      arr[i * 3 + 2] = n.pos.z * t;
    }
    posAttr.needsUpdate = true;
    void pointsRef;
  });

  return (
    <group rotation={[tiltX, 0, tiltZ]}>
      <group ref={groupRef}>
        {/* 궤도 선 */}
        <lineLoop geometry={ringGeo}>
          <lineBasicMaterial
            color="#2be6c8"
            transparent
            opacity={0.22}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </lineLoop>

        {/* 섹터 노드 + 라벨 (스프라이트라 회전해도 항상 정면).
            크기·밝기가 수급 점수에 확실히 비례 (0.07~0.30) → 1위가 눈에 띄게 큼 */}
        {nodes.map((n) => {
          const size = 0.07 + n.score * 0.23;
          return (
            <group key={n.name} position={n.pos}>
              <sprite scale={[size, size, 1]}>
                <spriteMaterial
                  map={glowTex}
                  color={n.color}
                  transparent
                  opacity={0.4 + n.score * 0.55}
                  blending={THREE.AdditiveBlending}
                  depthWrite={false}
                />
              </sprite>
              {/* 라벨은 작게+반투명 — 링 앞쪽(카메라 근접)에서 UI를 압도하지 않도록 */}
              <sprite position={[0, 0.11 + size * 0.5, 0]} scale={[0.32, 0.08, 1]}>
                <spriteMaterial map={n.label} transparent opacity={0.72} depthWrite={false} />
              </sprite>
            </group>
          );
        })}

        {/* 심장 → 섹터 파티클 */}
        <points ref={pointsRef} geometry={particle.geo}>
          <pointsMaterial
            map={glowTex}
            vertexColors
            size={0.09}
            sizeAttenuation
            transparent
            opacity={0.85}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </points>
      </group>
    </group>
  );
}

/** 심장 아래 홀로그램 프로젝터 디스크 */
function ProjectorBase({ glowTex }: { glowTex: THREE.Texture }) {
  const ringRef = useRef<THREE.Group>(null);
  useFrame(({ clock }, delta) => {
    if (!ringRef.current) return;
    ringRef.current.rotation.z += delta * 0.08;
    const pulse = 0.75 + Math.sin(clock.getElapsedTime() * 2.2) * 0.25;
    ringRef.current.children.forEach((ch, i) => {
      const mat = (ch as THREE.Mesh).material as THREE.MeshBasicMaterial;
      if (mat?.opacity !== undefined) mat.opacity = (i === 0 ? 0.42 : 0.2) * pulse;
    });
  });
  return (
    <group position={[0, -0.95, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <group ref={ringRef}>
        <mesh>
          <ringGeometry args={[1.02, 1.08, 64]} />
          <meshBasicMaterial
            color="#2be6c8"
            transparent
            opacity={0.42}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
            side={THREE.DoubleSide}
          />
        </mesh>
        <mesh>
          <ringGeometry args={[0.62, 0.645, 64]} />
          <meshBasicMaterial
            color="#2be6c8"
            transparent
            opacity={0.2}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
            side={THREE.DoubleSide}
          />
        </mesh>
      </group>
      {/* 바닥에서 퍼지는 부드러운 빛 */}
      <sprite scale={[3.2, 3.2, 1]}>
        <spriteMaterial
          map={glowTex}
          color="#1a9e8c"
          transparent
          opacity={0.16}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </sprite>
    </group>
  );
}

export function HoloSectorRings({ kr, us }: { kr: RingSector[]; us: RingSector[] }) {
  const glowTex = useMemo(() => makeGlowTexture(), []);
  useEffect(() => () => glowTex.dispose(), [glowTex]);

  return (
    <group>
      {/* 반경을 줄여 바깥 US 링까지 화면 안에 다 들어오게 (기존 2.3은 화면 반폭
          ~2.07을 넘겨 잘려서 커 보였다). tilt를 키워 세로 footprint도 압축.
          speed=0 = 자동회전 없음 → 12시가 항상 1위(수급 최상위). 회전은
          사용자가 OrbitControls로 카메라를 돌릴 때만 (심장과 함께 움직임). */}
      {kr.length > 0 && (
        <Ring sectors={kr} side="kr" radius={1.15} tiltX={0.5} tiltZ={0.08} speed={0} glowTex={glowTex} />
      )}
      {us.length > 0 && (
        <Ring sectors={us} side="us" radius={1.6} tiltX={0.5} tiltZ={-0.06} speed={0} glowTex={glowTex} />
      )}
      <ProjectorBase glowTex={glowTex} />
    </group>
  );
}
