import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

const defaultCameraPosition = new THREE.Vector3(30, 24, 30)
const focusPoint = new THREE.Vector3(0, 0, 0)

export const ThreeViewport = forwardRef(function ThreeViewport(
  { height = 560, compact = false },
  ref,
) {
  const mountRef = useRef(null)
  const cameraRef = useRef(null)
  const controlsRef = useRef(null)

  useImperativeHandle(ref, () => ({
    resetView() {
      if (!cameraRef.current || !controlsRef.current) return
      cameraRef.current.position.copy(defaultCameraPosition)
      controlsRef.current.target.copy(focusPoint)
      controlsRef.current.update()
    },
    focusSelected() {
      if (!controlsRef.current) return
      controlsRef.current.target.copy(focusPoint)
      controlsRef.current.update()
    },
  }))

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return undefined

    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(window.devicePixelRatio)
    renderer.setSize(mount.clientWidth, mount.clientHeight)
    mount.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    scene.background = new THREE.Color('#111827')

    const camera = new THREE.PerspectiveCamera(
      50,
      mount.clientWidth / mount.clientHeight,
      0.1,
      1000,
    )
    camera.position.copy(defaultCameraPosition)
    cameraRef.current = camera

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.target.copy(focusPoint)
    controls.enableDamping = true
    controlsRef.current = controls

    scene.add(new THREE.GridHelper(60, 30, '#3f3f46', '#27272a'))
    scene.add(new THREE.AxesHelper(8))

    const sampleGeometry = new THREE.Mesh(
      new THREE.CylinderGeometry(1.8, 1.8, 6, 24),
      new THREE.MeshStandardMaterial({ color: '#60a5fa' }),
    )
    sampleGeometry.position.set(0, 3, 0)
    scene.add(sampleGeometry)

    const key = new THREE.DirectionalLight('#ffffff', 1.2)
    key.position.set(8, 20, 10)
    scene.add(key)
    scene.add(new THREE.AmbientLight('#ffffff', 0.35))

    let frameId
    const animate = () => {
      frameId = window.requestAnimationFrame(animate)
      controls.update()
      renderer.render(scene, camera)
    }
    animate()

    const onResize = () => {
      if (!mount) return
      camera.aspect = mount.clientWidth / mount.clientHeight
      camera.updateProjectionMatrix()
      renderer.setSize(mount.clientWidth, mount.clientHeight)
    }

    window.addEventListener('resize', onResize)

    return () => {
      window.removeEventListener('resize', onResize)
      if (frameId) window.cancelAnimationFrame(frameId)
      controls.dispose()
      renderer.dispose()
      mount.removeChild(renderer.domElement)
    }
  }, [])

  const shellClass = compact ? 'viewport-shell compact' : 'viewport-shell'

  return (
    <div className={shellClass}>
      {!compact ? (
        <div className="viewport-label">Three.js + OrbitControls scaffold</div>
      ) : null}
      <div className="viewport-canvas" ref={mountRef} style={{ height }} />
    </div>
  )
})
