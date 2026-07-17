import { MeshReflectorMaterial } from '@react-three/drei';

/**
 * ReflectiveFloor — 심장 아래 어두운 반사 바닥.
 *
 * 그 AI 진단이 이미지2의 공간감 핵심으로 짚은 "바닥 반사"를 만든다.
 * 심장·오로라·파티클이 이 바닥에 은은하게 비쳐서 전경-중경-배경 레이어가
 * 실제로 존재하는 느낌 = 대기감/공간감.
 *
 * 성능 주의: MeshReflectorMaterial은 실시간 반사라 비용이 있다.
 * blur를 키우고 resolution을 낮추면 가벼워진다. 프레임 드롭 시 이 컴포넌트를
 * 통째로 빼는 게 가장 큰 성능 회복 (부모의 quality 단계에서 제어).
 */
interface ReflectiveFloorProps {
  /** 반사 해상도. 낮을수록 가벼움 (512=가벼움, 1024=중간, 2048=무거움) */
  resolution?: number;
  /** 흐림 정도. 크면 은은하고 가벼움 */
  blur?: number;
  /** 바닥 y 위치 (심장 아래로) */
  y?: number;
}

export function ReflectiveFloor({
  resolution = 1024,
  blur = 400,
  y = -2.2,
}: ReflectiveFloorProps) {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, y, 0]}>
      <planeGeometry args={[30, 30]} />
      <MeshReflectorMaterial
        blur={[blur, blur / 2]}
        resolution={resolution}
        mixBlur={1}
        mixStrength={12}      // 반사 강도 (너무 세면 거울, 약하면 은은)
        roughness={1}
        depthScale={1.2}
        minDepthThreshold={0.4}
        maxDepthThreshold={1.4}
        color="#050608"       // 거의 검은 바닥
        metalness={0.6}
        mirror={0.35}         // 0=반사없음, 1=완전거울. 은은하게
      />
    </mesh>
  );
}
