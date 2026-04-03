/**
 * Camera utilities for face recognition attendance.
 * Handles WebRTC camera access, frame capture, and API communication.
 */
class FaceCamera {
    constructor(videoElement, overlayCanvas) {
        this.video = videoElement;
        this.canvas = overlayCanvas;
        this.ctx = overlayCanvas.getContext('2d');
        this.stream = null;
        this.scanning = false;
        this.scanInterval = null;
    }

    async start() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480, facingMode: 'user' }
            });
            this.video.srcObject = this.stream;
            this.video.onloadedmetadata = () => {
                this.canvas.width = this.video.videoWidth;
                this.canvas.height = this.video.videoHeight;
            };
            return true;
        } catch (err) {
            console.error('Camera error:', err);
            return false;
        }
    }

    stop() {
        if (this.stream) {
            this.stream.getTracks().forEach(t => t.stop());
            this.stream = null;
        }
        this.stopScanning();
    }

    captureFrame(quality = 0.8) {
        const temp = document.createElement('canvas');
        temp.width = this.video.videoWidth;
        temp.height = this.video.videoHeight;
        temp.getContext('2d').drawImage(this.video, 0, 0);
        return temp.toDataURL('image/jpeg', quality);
    }

    drawBoundingBox(bbox, label, color = '#10b981') {
        this.ctx.strokeStyle = color;
        this.ctx.lineWidth = 3;
        this.ctx.strokeRect(bbox.left, bbox.top, bbox.right - bbox.left, bbox.bottom - bbox.top);

        if (label) {
            this.ctx.font = 'bold 14px Inter, sans-serif';
            const textWidth = this.ctx.measureText(label).width;
            this.ctx.fillStyle = color;
            this.ctx.fillRect(bbox.left, bbox.top - 24, textWidth + 12, 24);
            this.ctx.fillStyle = '#fff';
            this.ctx.fillText(label, bbox.left + 6, bbox.top - 7);
        }
    }

    clearOverlay() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }

    startScanning(callback, intervalMs = 2000) {
        this.scanning = true;
        this.scanInterval = setInterval(() => {
            if (this.scanning) callback();
        }, intervalMs);
    }

    stopScanning() {
        this.scanning = false;
        if (this.scanInterval) {
            clearInterval(this.scanInterval);
            this.scanInterval = null;
        }
        this.clearOverlay();
    }
}

// Export for use in templates
window.FaceCamera = FaceCamera;
