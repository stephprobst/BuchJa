<template>
  <div class="sketch-canvas-container">
    <div class="toolbar">
      <button 
        :class="{ active: currentTool === 'brush' }"
        @click="setTool('brush')"
        title="Brush"
      >
        ✏️ Brush
      </button>
      <button 
        :class="{ active: currentTool === 'eraser' }"
        @click="setTool('eraser')"
        title="Eraser"
      >
        🧹 Eraser
      </button>
      <button @click="clearCanvas" title="Clear">
        🗑️ Clear
      </button>
      <button @click="exportPng" title="Save" class="save-btn">
        💾 Save
      </button>
      
      <label class="brush-size">
        Size: 
        <input 
          type="range" 
          v-model="brushSize" 
          min="1" 
          max="50" 
          @input="updateBrushSize"
        />
        {{ brushSize }}px
      </label>
      
      <label class="color-picker">
        Color:
        <input 
          type="color" 
          v-model="brushColor" 
          @input="updateBrushColor"
        />
      </label>
    </div>
    
    <canvas ref="canvasEl"></canvas>
  </div>
</template>

<script>
export default {
  props: {
    width: {
      type: Number,
      default: 800
    },
    height: {
      type: Number,
      default: 600
    },
    backgroundColor: {
      type: String,
      default: '#ffffff'
    }
  },
  
  data() {
    return {
      canvas: null,
      currentTool: 'brush',
      brushSize: 5,
      brushColor: '#000000',
    };
  },
  
  mounted() {
    this.initCanvas();
    this.$emit('ready');
  },
  
  beforeUnmount() {
    if (this.canvas) {
      this.canvas.dispose();
    }
  },
  
  methods: {
    initCanvas() {
      // Load Fabric.js dynamically
      if (typeof fabric === 'undefined') {
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/fabric.js/5.3.1/fabric.min.js';
        script.onload = () => this.setupCanvas();
        document.head.appendChild(script);
      } else {
        this.setupCanvas();
      }
    },
    
    setupCanvas() {
      this.canvas = new fabric.Canvas(this.$refs.canvasEl, {
        width: this.width,
        height: this.height,
        backgroundColor: this.backgroundColor,
        isDrawingMode: true,
      });
      
      this.canvas.freeDrawingBrush.width = this.brushSize;
      this.canvas.freeDrawingBrush.color = this.brushColor;
    },
    
    setTool(tool) {
      this.currentTool = tool;
      if (!this.canvas) return;
      
      if (tool === 'eraser') {
        // Use white color as eraser on white background
        this.canvas.freeDrawingBrush.color = this.backgroundColor;
      } else {
        this.canvas.freeDrawingBrush.color = this.brushColor;
      }
    },
    
    updateBrushSize() {
      if (this.canvas) {
        this.canvas.freeDrawingBrush.width = parseInt(this.brushSize, 10);
      }
    },
    
    updateBrushColor() {
      if (this.canvas && this.currentTool === 'brush') {
        this.canvas.freeDrawingBrush.color = this.brushColor;
      }
    },
    
    clearCanvas() {
      if (this.canvas) {
        this.canvas.clear();
        this.canvas.backgroundColor = this.backgroundColor;
        this.canvas.renderAll();
      }
    },
    
    exportPng() {
      if (!this.canvas) return;
      
      const dataUrl = this.canvas.toDataURL({
        format: 'png',
        quality: 1.0,
      });
      
      // Emit event to parent (NiceGUI) with the image data
      this.$emit('save', dataUrl);
    },
    
    // Method callable from NiceGUI to get current canvas state
    getImageData() {
      if (!this.canvas) return null;
      return this.canvas.toDataURL({
        format: 'png',
        quality: 1.0,
      });
    },
    
    // Method callable from NiceGUI to load an image onto canvas
    loadImage(dataUrl) {
      if (!this.canvas) return;
      
      fabric.Image.fromURL(dataUrl, (img) => {
        this.canvas.clear();
        this.canvas.backgroundColor = this.backgroundColor;
        
        // Scale image to fit canvas
        const scale = Math.min(
          this.width / img.width,
          this.height / img.height
        );
        img.scale(scale);
        img.set({
          left: (this.width - img.width * scale) / 2,
          top: (this.height - img.height * scale) / 2,
        });
        
        this.canvas.add(img);
        this.canvas.renderAll();
      });
    },
  },
};
</script>

<style scoped>
.sketch-canvas-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 8px;
  background: #f5f5f5;
}

.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  padding: 5px;
  background: #fff;
  border-radius: 4px;
}

.toolbar button {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  transition: all 0.2s;
}

.toolbar button:hover {
  background: #e0e0e0;
}

.toolbar button.active {
  background: #1976d2;
  color: white;
  border-color: #1976d2;
}

.toolbar button.save-btn {
  background: #5898d4; /* NiceGUI default primary */
  color: white;
  border-color: #5898d4;
  font-weight: bold;
  margin-left: auto; /* Push to right if flex container allows, though toolbar is flex-wrap */
}

.toolbar button.save-btn:hover {
  background: #4a8ac6;
  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}

.brush-size, .color-picker {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 14px;
}

.brush-size input[type="range"] {
  width: 100px;
}

canvas {
  border: 1px solid #999;
  border-radius: 4px;
  cursor: crosshair;
}
</style>
