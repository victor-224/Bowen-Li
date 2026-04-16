import { useEffect, useMemo, useRef } from 'react'
import { Canvas, useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { Vector3 } from 'three'

function mapToScenePosition(item) {
  const x = item.position.x ?? 0
  const z = item.position.y ?? 0
  const y = 0
  return [x, y, z]
}

function dimensionsFor(item) {
  return {
    diameter: item.dimensions.diameterM ?? 1.4,
    length: item.dimensions.lengthM ?? 2.5,
    width: item.dimensions.widthM ?? 2,
    height: item.dimensions.heightM ?? 2,
  }
}

function EquipmentMesh({ item, selected, onSelect }) {
  const baseColor = item.position.status === 'unresolved' ? '#d97706' : '#64748b'
  const color = selected ? '#4f46e5' : baseColor
  const [x, y, z] = mapToScenePosition(item)
  const dims = dimensionsFor(item)
  const rotationY = ((item.position.rotationDeg ?? item.orientationDeg) * Math.PI) / 180

  if (item.geometryPrimitive === 'vertical-cylinder') {
    return (
      <mesh position={[x, y + dims.height / 2, z]} onClick={onSelect}>
        <cylinderGeometry args={[dims.diameter / 2, dims.diameter / 2, dims.height, 24]} />
        <meshStandardMaterial color={color} />
      </mesh>
    )
  }

  if (item.geometryPrimitive === 'horizontal-cylinder') {
    return (
      <mesh
        position={[x, y + dims.diameter / 2, z]}
        rotation={[0, rotationY, Math.PI / 2]}
        onClick={onSelect}
      >
        <cylinderGeometry args={[dims.diameter / 2, dims.diameter / 2, dims.length, 24]} />
        <meshStandardMaterial color={color} />
      </mesh>
    )
  }

  if (item.geometryPrimitive === 'box') {
    return (
      <mesh position={[x, y + dims.height / 2, z]} rotation={[0, rotationY, 0]} onClick={onSelect}>
        <boxGeometry args={[dims.length, dims.height, dims.width]} />
        <meshStandardMaterial color={color} />
      </mesh>
    )
  }

  return (
    <mesh position={[x, y + 0.6, z]} onClick={onSelect}>
      <sphereGeometry args={[0.6, 18, 18]} />
      <meshStandardMaterial color={color} />
    </mesh>
  )
}

function CameraController({ command, selectedItem }) {
  const controlsRef = useRef(null)
  const { camera } = useThree()

  useEffect(() => {
    if (!command || !controlsRef.current) {
      return
    }

    if (command.type === 'reset') {
      camera.position.set(14, 12, 14)
      controlsRef.current.target.set(0, 0, 0)
      controlsRef.current.update()
      return
    }

    if (command.type === 'focus' && selectedItem) {
      const x = selectedItem.position.x ?? 0
      const z = selectedItem.position.y ?? 0
      const target = new Vector3(x, 0, z)
      controlsRef.current.target.copy(target)
      camera.position.set(x + 8, 7, z + 8)
      controlsRef.current.update()
    }
  }, [camera, command, selectedItem])

  return <OrbitControls ref={controlsRef} makeDefault />
}

export function EquipmentScene({
  equipment,
  selectedId,
  onSelect,
  cameraCommand,
  selectedItem,
}) {
  const sceneItems = useMemo(() => equipment, [equipment])

  return (
    <Canvas camera={{ position: [14, 12, 14], fov: 45 }}>
      <color attach="background" args={['#f8fafc']} />
      <ambientLight intensity={0.7} />
      <directionalLight position={[8, 12, 4]} intensity={1.1} />
      <gridHelper args={[60, 60, '#cbd5e1', '#e2e8f0']} />
      <axesHelper args={[6]} />

      {sceneItems.map((item) => (
        <EquipmentMesh
          key={item.id}
          item={item}
          selected={selectedId === item.id}
          onSelect={() => onSelect(item.id)}
        />
      ))}

      <CameraController command={cameraCommand} selectedItem={selectedItem} />
    </Canvas>
  )
}
