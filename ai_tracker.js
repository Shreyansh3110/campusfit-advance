document.addEventListener("DOMContentLoaded", () => {
    const videoElement = document.getElementsByClassName('input_video')[0];
    const canvasElement = document.getElementsByClassName('output_canvas')[0];
    const canvasCtx = canvasElement.getContext('2d');
    
    const repCountEl = document.getElementById('repCount');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const loadingText = document.getElementById('loadingText');
    const btnStart = document.getElementById('btnStartCamera');
    const btnStop = document.getElementById('btnStopCamera');
    const btnSave = document.getElementById('btnSaveWorkout');
    const workoutMinutesInput = document.getElementById('workoutMinutes');
    const feedbackToast = document.getElementById('feedbackToast');

    let camera = null;
    let repCount = 0;
    let poseState = "up"; // "up" or "down"
    
    // Utility function to calculate angle between 3 points
    function calculateAngle(a, b, c) {
        const radians = Math.atan2(c.y - b.y, c.x - b.x) - Math.atan2(a.y - b.y, a.x - b.x);
        let angle = Math.abs((radians * 180.0) / Math.PI);
        if (angle > 180.0) {
            angle = 360.0 - angle;
        }
        return angle;
    }

    function showFeedback(msg) {
        feedbackToast.textContent = msg;
        feedbackToast.classList.add('show');
        setTimeout(() => feedbackToast.classList.remove('show'), 1500);
    }

    function onResults(results) {
        // Hide loading overlay once video starts rendering
        if (loadingOverlay.style.display !== 'none') {
            loadingOverlay.style.display = 'none';
        }

        canvasCtx.save();
        canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);
        
        // Draw the video frame
        canvasCtx.drawImage(results.image, 0, 0, canvasElement.width, canvasElement.height);

        if (results.poseLandmarks) {
            // Draw skeleton
            drawConnectors(canvasCtx, results.poseLandmarks, POSE_CONNECTIONS,
                           {color: '#00ffc8', lineWidth: 4});
            drawLandmarks(canvasCtx, results.poseLandmarks,
                          {color: '#ff0055', lineWidth: 2, radius: 4});

            // Squat Logic (Left Leg)
            const leftHip = results.poseLandmarks[23];
            const leftKnee = results.poseLandmarks[25];
            const leftAnkle = results.poseLandmarks[27];

            // Ensure points are visible
            if (leftHip.visibility > 0.5 && leftKnee.visibility > 0.5 && leftAnkle.visibility > 0.5) {
                const angle = calculateAngle(leftHip, leftKnee, leftAnkle);

                // State Machine for Squat
                if (angle > 160) {
                    if (poseState === "down") {
                        repCount += 1;
                        repCountEl.textContent = repCount;
                        showFeedback("Good rep! 🔥");
                        
                        // Enable save button if > 0 reps
                        btnSave.disabled = false;
                        // For demo, 5 reps = 1 minute of activity logged
                        workoutMinutesInput.value = Math.max(1, Math.floor(repCount / 5));
                    }
                    poseState = "up";
                } else if (angle < 100) {
                    poseState = "down";
                }
            }
        }
        canvasCtx.restore();
    }

    const pose = new Pose({locateFile: (file) => {
        return `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`;
    }});
    
    pose.setOptions({
        modelComplexity: 1,
        smoothLandmarks: true,
        enableSegmentation: false,
        smoothSegmentation: false,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5
    });
    
    pose.onResults(onResults);

    btnStart.addEventListener('click', async () => {
        btnStart.style.display = 'none';
        btnStop.style.display = 'block';
        loadingOverlay.style.display = 'flex';
        loadingText.textContent = "Starting Camera...";
        
        camera = new Camera(videoElement, {
            onFrame: async () => {
                await pose.send({image: videoElement});
            },
            width: 640,
            height: 480
        });
        camera.start();
    });

    btnStop.addEventListener('click', () => {
        if (camera) {
            camera.stop();
            camera = null;
        }
        btnStop.style.display = 'none';
        btnStart.style.display = 'block';
        
        // Clear canvas
        canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);
        canvasCtx.fillStyle = "#000";
        canvasCtx.fillRect(0, 0, canvasElement.width, canvasElement.height);
    });
});
