/* Minimal GLB 2.0 loader for the generated Inhabit Space relics. */
(function () {
  const COMPONENT = {
    5120: Int8Array,
    5121: Uint8Array,
    5122: Int16Array,
    5123: Uint16Array,
    5125: Uint32Array,
    5126: Float32Array,
  };
  const SIZE = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT4: 16 };
  const ATTRIBUTE = {
    POSITION: "position",
    NORMAL: "normal",
    TEXCOORD_0: "uv",
    COLOR_0: "color",
    TANGENT: "tangent",
  };

  function chunked(buffer) {
    const view = new DataView(buffer);
    if (view.getUint32(0, true) !== 0x46546c67 || view.getUint32(4, true) !== 2) {
      throw new Error("Relic is not a GLB 2.0 asset");
    }
    let offset = 12;
    let document = null;
    let binary = null;
    while (offset < buffer.byteLength) {
      const length = view.getUint32(offset, true);
      const type = view.getUint32(offset + 4, true);
      const bytes = buffer.slice(offset + 8, offset + 8 + length);
      if (type === 0x4e4f534a) {
        document = JSON.parse(new TextDecoder().decode(bytes).replace(/\0+$/, ""));
      } else if (type === 0x004e4942) binary = bytes;
      offset += 8 + length;
    }
    if (!document || !binary) throw new Error("Relic GLB is missing JSON or binary data");
    return { document, binary };
  }

  function accessor(document, binary, index) {
    const source = document.accessors[index];
    const view = document.bufferViews[source.bufferView];
    const Type = COMPONENT[source.componentType];
    const itemSize = SIZE[source.type];
    const componentBytes = Type.BYTES_PER_ELEMENT;
    const byteOffset = (view.byteOffset || 0) + (source.byteOffset || 0);
    const stride = view.byteStride || itemSize * componentBytes;
    let array;
    if (stride === itemSize * componentBytes) {
      array = new Type(binary, byteOffset, source.count * itemSize);
    } else {
      array = new Type(source.count * itemSize);
      const data = new DataView(binary, byteOffset, source.count * stride);
      const getter = {
        5120: "getInt8",
        5121: "getUint8",
        5122: "getInt16",
        5123: "getUint16",
        5125: "getUint32",
        5126: "getFloat32",
      }[source.componentType];
      for (let row = 0; row < source.count; row += 1) {
        for (let col = 0; col < itemSize; col += 1) {
          array[row * itemSize + col] = data[getter](
            row * stride + col * componentBytes,
            componentBytes > 1
          );
        }
      }
    }
    return new THREE.BufferAttribute(array, itemSize, !!source.normalized);
  }

  async function imageTexture(document, binary, index) {
    const textureSpec = document.textures[index];
    const image = document.images[textureSpec.source];
    const view = document.bufferViews[image.bufferView];
    const start = view.byteOffset || 0;
    const blob = new Blob([binary.slice(start, start + view.byteLength)], {
      type: image.mimeType,
    });
    const bitmap = await createImageBitmap(blob);
    const texture = new THREE.Texture(bitmap);
    texture.flipY = false;
    texture.needsUpdate = true;
    const sampler = (document.samplers || [])[textureSpec.sampler] || {};
    const wraps = {
      33071: THREE.ClampToEdgeWrapping,
      33648: THREE.MirroredRepeatWrapping,
      10497: THREE.RepeatWrapping,
    };
    texture.wrapS = wraps[sampler.wrapS] || THREE.RepeatWrapping;
    texture.wrapT = wraps[sampler.wrapT] || THREE.RepeatWrapping;
    texture.magFilter = sampler.magFilter === 9728 ? THREE.NearestFilter : THREE.LinearFilter;
    texture.minFilter = {
      9728: THREE.NearestFilter,
      9729: THREE.LinearFilter,
      9984: THREE.NearestMipmapNearestFilter,
      9985: THREE.LinearMipmapNearestFilter,
      9986: THREE.NearestMipmapLinearFilter,
      9987: THREE.LinearMipmapLinearFilter,
    }[sampler.minFilter] || THREE.LinearMipmapLinearFilter;
    return texture;
  }

  function factorColor(factor, fallback) {
    return new THREE.Color(...(factor || fallback));
  }

  function material(document, spec, textures) {
    const pbr = spec.pbrMetallicRoughness || {};
    const base = pbr.baseColorFactor || [1, 1, 1, 1];
    const extensions = spec.extensions || {};
    const specular = extensions.KHR_materials_specular || {};
    const volume = extensions.KHR_materials_volume || {};
    const transmission = extensions.KHR_materials_transmission || {};
    const result = new THREE.MeshPhysicalMaterial({
      name: spec.name || "relic material",
      color: factorColor(base.slice(0, 3), [1, 1, 1]),
      opacity: base[3],
      transparent: spec.alphaMode === "BLEND" || base[3] < 1,
      alphaTest: spec.alphaMode === "MASK" ? spec.alphaCutoff || 0.5 : 0,
      side: spec.doubleSided ? THREE.DoubleSide : THREE.FrontSide,
      metalness: pbr.metallicFactor === undefined ? 1 : pbr.metallicFactor,
      roughness: pbr.roughnessFactor === undefined ? 1 : pbr.roughnessFactor,
      specularIntensity: specular.specularFactor === undefined ? 1 : specular.specularFactor,
      specularColor: factorColor(specular.specularColorFactor, [1, 1, 1]),
      transmission: transmission.transmissionFactor || 0,
      thickness: volume.thicknessFactor || 0,
      attenuationDistance: volume.attenuationDistance || Infinity,
      attenuationColor: factorColor(volume.attenuationColor, [1, 1, 1]),
      envMapIntensity: 1.35,
    });
    if (pbr.baseColorTexture) {
      result.map = textures[pbr.baseColorTexture.index];
      result.map.colorSpace = THREE.SRGBColorSpace;
    }
    if (pbr.metallicRoughnessTexture) {
      const packed = textures[pbr.metallicRoughnessTexture.index];
      result.metalnessMap = packed;
      result.roughnessMap = packed;
    }
    if (spec.normalTexture) {
      result.normalMap = textures[spec.normalTexture.index];
      const scale = spec.normalTexture.scale === undefined ? 1 : spec.normalTexture.scale;
      result.normalScale.set(scale, scale);
    }
    if (spec.emissiveTexture) result.emissiveMap = textures[spec.emissiveTexture.index];
    if (spec.emissiveFactor) result.emissive.setRGB(...spec.emissiveFactor);
    result.needsUpdate = true;
    return result;
  }

  async function parse(buffer) {
    const { document, binary } = chunked(buffer);
    const textures = await Promise.all(
      (document.textures || []).map((_, index) => imageTexture(document, binary, index))
    );
    const materials = (document.materials || []).map((item) =>
      material(document, item, textures)
    );
    const meshes = (document.meshes || []).map((meshSpec) => {
      const group = new THREE.Group();
      group.name = meshSpec.name || "relic mesh";
      for (const primitive of meshSpec.primitives) {
        const geometry = new THREE.BufferGeometry();
        for (const [semantic, index] of Object.entries(primitive.attributes || {})) {
          if (ATTRIBUTE[semantic]) {
            geometry.setAttribute(ATTRIBUTE[semantic], accessor(document, binary, index));
          }
        }
        if (primitive.indices !== undefined) {
          geometry.setIndex(accessor(document, binary, primitive.indices));
        }
        geometry.computeBoundingSphere();
        const mesh = new THREE.Mesh(
          geometry,
          materials[primitive.material] || new THREE.MeshStandardMaterial()
        );
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        group.add(mesh);
      }
      return group;
    });
    const root = new THREE.Group();
    const roots = ((document.scenes || [])[document.scene || 0] || {}).nodes || [];
    function buildNode(index) {
      const spec = document.nodes[index];
      const node = spec.mesh === undefined ? new THREE.Group() : meshes[spec.mesh].clone();
      node.name = spec.name || "relic node";
      if (spec.matrix) node.matrix.fromArray(spec.matrix).decompose(node.position, node.quaternion, node.scale);
      if (spec.translation) node.position.fromArray(spec.translation);
      if (spec.rotation) node.quaternion.fromArray(spec.rotation);
      if (spec.scale) node.scale.fromArray(spec.scale);
      for (const child of spec.children || []) node.add(buildNode(child));
      return node;
    }
    for (const index of roots) root.add(buildNode(index));
    return root;
  }

  const cache = new Map();
  async function load(url) {
    if (!cache.has(url)) {
      cache.set(
        url,
        fetch(url)
          .then((response) => {
            if (!response.ok) throw new Error(`Could not load relic: ${response.status}`);
            return response.arrayBuffer();
          })
          .then(parse)
      );
    }
    const original = await cache.get(url);
    const clone = original.clone(true);
    clone.traverse((object) => {
      if (object.material) object.material = object.material.clone();
    });
    return clone;
  }

  window.RelicGLBLoader = { load };
})();
