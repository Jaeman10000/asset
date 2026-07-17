import * as THREE from 'three';
import { mergeGeometries, mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';

/**
 * placeholderHeart — Meshy GLB(`public/models/heart.glb`)가 아직 없을 때 쓰는
 * 절차적 심장 지오메트리.
 *
 * 좌/우 심실 + 좌/우 심방 + 대동맥 줄기를 구/튜브로 합치고 아래쪽을 심첨(apex)
 * 형태로 조여서 "해부학적 심장의 실루엣"만 흉내낸다. 유리질 재질/박동/조명
 * 파이프라인을 GLB 없이 검증하기 위한 것.
 *
 * heart.glb를 public/models/에 넣으면 HeartCore가 자동으로 GLB를 쓰고
 * 이 지오메트리는 더 이상 사용되지 않는다.
 */
export function createPlaceholderHeartGeometry(): THREE.BufferGeometry {
  const parts: THREE.BufferGeometry[] = [];

  const addBlob = (
    radius: number,
    segments: [number, number],
    scale: [number, number, number],
    position: [number, number, number]
  ) => {
    const geo = new THREE.SphereGeometry(radius, segments[0], segments[1]);
    geo.scale(...scale);
    geo.translate(...position);
    parts.push(geo);
  };

  // 좌심실 (주 덩어리, 오른쪽 아래로 크게)
  addBlob(0.78, [48, 32], [0.98, 1.28, 0.92], [0.16, -0.12, 0]);
  // 우심실 (왼쪽에 붙는 보조 덩어리)
  addBlob(0.6, [40, 28], [0.9, 1.05, 0.86], [-0.34, 0.02, 0.04]);
  // 좌심방 / 우심방 (위쪽 작은 덩어리 둘)
  addBlob(0.4, [32, 24], [1, 0.92, 0.95], [0.34, 0.62, -0.06]);
  addBlob(0.34, [32, 24], [1, 0.9, 0.9], [-0.32, 0.56, 0.1]);

  // 대동맥 줄기 (위에서 뒤로 휘어지는 튜브)
  const aortaCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(0.05, 0.5, 0),
    new THREE.Vector3(0.0, 0.95, -0.02),
    new THREE.Vector3(-0.24, 1.14, -0.1),
  ]);
  parts.push(new THREE.TubeGeometry(aortaCurve, 12, 0.17, 16, false));

  const merged = mergeGeometries(
    parts.map((p) => p.toNonIndexed()),
    false
  );

  // 아래로 갈수록 조여서 심첨(apex) 실루엣 만들기
  const posAttr = merged.attributes.position as THREE.BufferAttribute;
  for (let i = 0; i < posAttr.count; i++) {
    const y = posAttr.getY(i);
    if (y < 0) {
      const t = Math.min(1, -y / 1.5);
      const squeeze = 1 - 0.45 * t * t;
      posAttr.setX(i, posAttr.getX(i) * squeeze);
      posAttr.setZ(i, posAttr.getZ(i) * squeeze);
      posAttr.setY(i, y * 1.12);
    }
  }

  // 같은 위치의 정점을 용접해 부드러운 법선(유리질 표면에 필수)을 얻는다
  const smooth = mergeVertices(merged, 1e-4);
  smooth.computeVertexNormals();
  smooth.rotateZ(-0.18); // 실제 심장처럼 살짝 기울임
  smooth.center();
  return smooth;
}
