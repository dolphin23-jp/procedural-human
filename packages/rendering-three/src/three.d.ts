declare module 'three' {
  export class Vector3 {
    x: number;
    y: number;
    z: number;
    constructor(x?: number, y?: number, z?: number);
    set(x: number, y: number, z: number): this;
    copy(v: Vector3): this;
    normalize(): this;
  }
  export class Matrix4 {
    set(
      n11: number,
      n12: number,
      n13: number,
      n14: number,
      n21: number,
      n22: number,
      n23: number,
      n24: number,
      n31: number,
      n32: number,
      n33: number,
      n34: number,
      n41: number,
      n42: number,
      n43: number,
      n44: number,
    ): this;
    copy(matrix: Matrix4): this;
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
    readonly up: Vector3;
    readonly matrix: Matrix4;
    matrixAutoUpdate: boolean;
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
    readonly target: Object3D;
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
