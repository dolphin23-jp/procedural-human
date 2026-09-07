declare module 'three' {
  export class Vector3 {
    constructor(x?: number, y?: number, z?: number);
    set(x: number, y: number, z: number): this;
  }
  export class Euler {
    x: number;
    y: number;
    z: number;
  }
  export class Object3D {
    readonly children: Object3D[];
    readonly position: Vector3;
    readonly rotation: Euler;
    name: string;
    userData: Record<string, unknown>;
    add(...objects: Object3D[]): this;
  }
  export class Group extends Object3D {}
  export class Scene extends Object3D {
    background: Color | null;
  }
  export class BufferGeometry {
    dispose(): void;
  }
  export class BoxGeometry extends BufferGeometry {
    constructor(width?: number, height?: number, depth?: number);
  }
  export class CylinderGeometry extends BufferGeometry {
    constructor(
      radiusTop?: number,
      radiusBottom?: number,
      height?: number,
      radialSegments?: number,
    );
  }
  export class Material {
    dispose(): void;
  }
  export class MeshStandardMaterial extends Material {
    constructor(parameters?: {
      color?: number;
      opacity?: number;
      roughness?: number;
      metalness?: number;
      transparent?: boolean;
      depthWrite?: boolean;
    });
  }
  export class Mesh extends Object3D {
    constructor(geometry?: BufferGeometry, material?: Material);
    readonly geometry: BufferGeometry;
    readonly material: Material | Material[];
  }
  export class Color {
    constructor(color?: number);
  }
  export class AmbientLight extends Object3D {
    constructor(color?: number, intensity?: number);
  }
  export class DirectionalLight extends Object3D {
    constructor(color?: number, intensity?: number);
  }
  export class PerspectiveCamera extends Object3D {
    constructor(fov?: number, aspect?: number, near?: number, far?: number);
    aspect: number;
    lookAt(x: number, y: number, z: number): void;
    updateProjectionMatrix(): void;
  }
  export class WebGLRenderer {
    constructor(parameters?: {
      canvas?: HTMLCanvasElement;
      antialias?: boolean;
      alpha?: boolean;
    });
    setPixelRatio(value: number): void;
    setSize(width: number, height: number, updateStyle?: boolean): void;
    render(scene: Scene, camera: PerspectiveCamera): void;
    dispose(): void;
  }
}
