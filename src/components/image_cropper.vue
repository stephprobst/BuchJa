<template>
  <div class="image-cropper-container">
    <div class="toolbar" v-if="imageLoaded">
      <button @click="rotateLeft" title="Rotate Left">
        ↺ Rotate Left
      </button>
      <button @click="rotateRight" title="Rotate Right">
        ↻ Rotate Right
      </button>
      <button @click="flipHorizontal" title="Flip Horizontal">
        ↔ Flip H
      </button>
      <button @click="flipVertical" title="Flip Vertical">
        ↕ Flip V
      </button>
      <button @click="reset" title="Reset">
        🔄 Reset
      </button>
      <button @click="cropAndSave" class="primary" title="Crop & Save">
        ✂️ Crop & Save
      </button>
      
      <label class="aspect-ratio-select">
        Aspect Ratio:
        <select v-model="aspectRatioOption" @change="updateAspectRatio">
          <option value="free">Free</option>
          <option value="1:1">1:1</option>
          <option value="3:4">3:4</option>
          <option value="4:3">4:3</option>
          <option value="9:16">9:16</option>
          <option value="16:9">16:9</option>
        </select>
      </label>
    </div>
    
    <div class="cropper-wrapper" ref="cropperWrapper">
      <img 
        ref="imageEl" 
        :src="imageSrc" 
        @load="onImageLoad"
        v-show="imageSrc"
        style="max-width: 100%; max-height: 100%; display: block;"
      />
      <div v-if="!imageSrc" class="placeholder">
        Select an image to crop
      </div>
    </div>
  </div>
</template>

<script>
export default {
  props: {
    initialAspectRatio: {
      type: String,
      default: 'free'
    },
    uploadId: {
      type: String,
      required: true
    }
  },
  
  data() {
    return {
      cropper: null,
      imageSrc: null,
      imageLoaded: false,
      aspectRatioOption: 'free',
      cropperReady: false,
    };
  },
  
  mounted() {
    this.aspectRatioOption = this.initialAspectRatio;
    this.loadCropperJs();
    this.$emit('ready');
  },
  
  beforeUnmount() {
    this.destroyCropper();
  },
  
  methods: {
    loadCropperJs() {
      // Load Cropper.js dynamically if not already loaded
      if (typeof Cropper === 'undefined') {
        // Load CSS
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = 'https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.css';
        document.head.appendChild(link);
        
        // Load JS
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.js';
        script.onload = () => {
          this.cropperReady = true;
          if (this.imageSrc) {
            this.$nextTick(() => this.initCropper());
          }
        };
        document.head.appendChild(script);
      } else {
        this.cropperReady = true;
      }
    },
    
    loadImage(src) {
      // Destroy existing cropper first
      this.destroyCropper();
      
      // If loading the same image, force a reload by clearing first
      if (this.imageSrc === src) {
        this.imageSrc = null;
        this.imageLoaded = false;
        this.$nextTick(() => {
          this.imageSrc = src;
        });
      } else {
        this.imageSrc = src;
        this.imageLoaded = false;
      }
    },
    
    onImageLoad() {
      this.imageLoaded = true;
      if (this.cropperReady) {
        this.$nextTick(() => this.initCropper());
      }
    },
    
    initCropper() {
      // Only check for imageEl - cropper should be null after destroyCropper
      if (!this.$refs.imageEl) return;
      // Don't reinitialize if already exists
      if (this.cropper) return;
      
      const aspectRatio = this.parseAspectRatio(this.aspectRatioOption);
      
      this.cropper = new Cropper(this.$refs.imageEl, {
        aspectRatio: aspectRatio,
        viewMode: 1,
        dragMode: 'crop',
        autoCropArea: 0.8,
        restore: false,
        guides: true,
        center: true,
        highlight: true,
        cropBoxMovable: true,
        cropBoxResizable: true,
        toggleDragModeOnDblclick: false,
        responsive: true,
      });
    },
    
    destroyCropper() {
      if (this.cropper) {
        this.cropper.destroy();
        this.cropper = null;
      }
    },
    
    parseAspectRatio(option) {
      if (option === 'free' || !option) return NaN;
      const parts = option.split(':');
      if (parts.length === 2) {
        return parseFloat(parts[0]) / parseFloat(parts[1]);
      }
      return NaN;
    },
    
    updateAspectRatio() {
      if (this.cropper) {
        const ratio = this.parseAspectRatio(this.aspectRatioOption);
        this.cropper.setAspectRatio(ratio);
      }
    },
    
    setAspectRatio(ratio) {
      this.aspectRatioOption = ratio;
      this.updateAspectRatio();
    },
    
    rotateLeft() {
      if (this.cropper) {
        this.cropper.rotate(-90);
      }
    },
    
    rotateRight() {
      if (this.cropper) {
        this.cropper.rotate(90);
      }
    },
    
    flipHorizontal() {
      if (this.cropper) {
        const data = this.cropper.getData();
        this.cropper.scaleX(data.scaleX === -1 ? 1 : -1);
      }
    },
    
    flipVertical() {
      if (this.cropper) {
        const data = this.cropper.getData();
        this.cropper.scaleY(data.scaleY === -1 ? 1 : -1);
      }
    },
    
    reset() {
      if (this.cropper) {
        this.cropper.reset();
      }
    },
    
    async cropAndSave() {
      if (!this.cropper) {
        this.$emit('error', 'No cropper initialized');
        return;
      }
      
      const canvas = this.cropper.getCroppedCanvas({
        imageSmoothingEnabled: true,
        imageSmoothingQuality: 'high',
      });
      
      if (!canvas) {
        this.$emit('error', 'Failed to get cropped canvas');
        return;
      }
      
      // Use full quality PNG - no compression needed since we're using HTTP POST
      const dataUrl = canvas.toDataURL('image/png', 1.0);
      
      // Send via HTTP POST to bypass websocket payload limits
      try {
        const response = await fetch(`/api/crop-upload/${this.uploadId}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'text/plain',
          },
          body: dataUrl,
        });
        
        if (!response.ok) {
          throw new Error(`HTTP error: ${response.status}`);
        }
        
        const result = await response.json();
        if (result.status !== 'ok') {
          throw new Error(result.message || 'Upload failed');
        }
      } catch (error) {
        console.error('Failed to upload cropped image:', error);
        this.$emit('error', `Failed to save cropped image: ${error.message}`);
      }
    },
    
    // Method callable from NiceGUI to get cropped image
    getCroppedImage() {
      if (!this.cropper) return null;
      
      const canvas = this.cropper.getCroppedCanvas({
        imageSmoothingEnabled: true,
        imageSmoothingQuality: 'high',
      });
      
      if (!canvas) return null;
      return canvas.toDataURL('image/png', 1.0);
    },
    
    // Clear the cropper and image
    clear() {
      this.destroyCropper();
      this.imageSrc = null;
      this.imageLoaded = false;
    },
  },
};
</script>

<style scoped>
.image-cropper-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  padding: 8px;
  background: #f5f5f5;
  border-radius: 4px;
}

.toolbar button {
  padding: 6px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.toolbar button:hover {
  background: #e0e0e0;
}

.toolbar button.primary {
  background: #1976d2;
  color: white;
  border-color: #1976d2;
}

.toolbar button.primary:hover {
  background: #1565c0;
}

.aspect-ratio-select {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
}

.aspect-ratio-select select {
  padding: 4px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.cropper-wrapper {
  width: 100%;
  min-height: 300px;
  max-height: 500px;
  background: #f0f0f0;
  border: 1px solid #ddd;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.placeholder {
  color: #999;
  font-size: 14px;
}
</style>
