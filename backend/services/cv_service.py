# backend/services/cv_service.py
import cv2
import numpy as np
import base64
from typing import List, Dict, Any, Tuple, Optional
import math
import os  # For checking model file existence

# Attempt to import TFLite runtime
try:
    import tflite_runtime.interpreter as tflite

    print("INFO: TensorFlow Lite runtime (tflite_runtime) imported successfully.")
except ImportError:
    try:
        import tensorflow.lite as tflite  # Fallback for full TensorFlow if tflite_runtime is not installed

        print("INFO: TensorFlow Lite (from tensorflow.lite) imported successfully.")
    except ImportError:
        tflite = None
        print(
            "CRITICAL WARNING: TensorFlow Lite runtime (tflite_runtime or from tensorflow.lite) NOT FOUND. CV service will be NON-FUNCTIONAL.")

from backend.core.config import settings

# --- Pose Estimation Model Constants (Example for MoveNet SinglePose Lightning) ---
MODEL_INPUT_SIZE = (192, 192)  # (height, width) for MoveNet Lightning. Thunder is (256,256)
NUM_KEYPOINTS = 17  # MoveNet returns 17 keypoints
MIN_CROP_KEYPOINT_SCORE = 0.2
MIN_KEYPOINT_VISIBILITY_SCORE = 0.3  # Threshold for considering a keypoint valid for angle calculations

KEYPOINT_DICT = {
    'nose': 0, 'left_eye': 1, 'right_eye': 2, 'left_ear': 3, 'right_ear': 4,
    'left_shoulder': 5, 'right_shoulder': 6, 'left_elbow': 7, 'right_elbow': 8,
    'left_wrist': 9, 'right_wrist': 10, 'left_hip': 11, 'right_hip': 12,
    'left_knee': 13, 'right_knee': 14, 'left_ankle': 15, 'right_ankle': 16
}


class PoseEstimator:
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self.is_input_float = False
        self.model_input_height = MODEL_INPUT_SIZE[0]  # Default, will be overridden
        self.model_input_width = MODEL_INPUT_SIZE[1]  # Default, will be overridden

        if tflite is None:
            print(
                f"ERROR: TFLite runtime not available. PoseEstimator cannot be initialized for model: {self.model_path}")
            return

        if not os.path.exists(self.model_path):
            print(f"ERROR: Model file not found at path: {self.model_path}. PoseEstimator cannot be initialized.")
            print(f"  Please ensure the model file exists and POSE_ESTIMATION_MODEL_PATH in .env is correct.")
            return

        try:
            print(f"INFO: Attempting to load TFLite model from: {self.model_path}")
            self.interpreter = tflite.Interpreter(model_path=self.model_path)
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()

            self.is_input_float = self.input_details[0]['dtype'] == np.float32
            # Expected shape for MoveNet: [1, height, width, 3]
            self.model_input_height = self.input_details[0]['shape'][1]
            self.model_input_width = self.input_details[0]['shape'][2]

            print(f"INFO: Pose estimation model loaded successfully: {self.model_path}")
            print(f"  Input Shape: {self.input_details[0]['shape']}, Type: {self.input_details[0]['dtype']}")
            print(f"  Output Shape: {self.output_details[0]['shape']}, Type: {self.output_details[0]['dtype']}")

        except Exception as e:
            print(f"ERROR: Failed to load TFLite model from '{self.model_path}': {e}")
            self.interpreter = None  # Ensure interpreter is None on failure

    def _preprocess_image(self, image_bytes: bytes) -> Optional[Tuple[np.ndarray, Tuple[int, int]]]:
        try:
            image_np = np.frombuffer(image_bytes, np.uint8)
            image_bgr = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
            if image_bgr is None:
                print("Warning: Could not decode image bytes.")
                return None

            original_height, original_width = image_bgr.shape[:2]
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

            input_image_resized = cv2.resize(image_rgb, (self.model_input_width, self.model_input_height))

            input_data = np.expand_dims(input_image_resized, axis=0)

            if self.is_input_float and input_data.dtype == np.uint8:
                input_data = input_data.astype(np.float32)
            elif not self.is_input_float and input_data.dtype == np.float32:  # Model expects uint8
                input_data = np.clip(input_data, 0, 255).astype(np.uint8)

            return input_data, (original_height, original_width)
        except Exception as e:
            print(f"Error during image preprocessing: {e}")
            return None

    def run_inference(self, image_bytes: bytes) -> Optional[np.ndarray]:
        if not self.interpreter:
            print("Warning: Pose estimator model not loaded or initialized correctly. Cannot run inference.")
            return None

        preprocess_result = self._preprocess_image(image_bytes)
        if preprocess_result is None:
            return None
        input_data, _ = preprocess_result

        self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
        self.interpreter.invoke()

        keypoints_with_scores = self.interpreter.get_tensor(self.output_details[0]['index'])
        return keypoints_with_scores.squeeze() if keypoints_with_scores.ndim > 2 else keypoints_with_scores


pose_estimator_instance: Optional[PoseEstimator] = None
if tflite is not None:
    model_file_path_from_settings = settings.POSE_ESTIMATION_MODEL_PATH
    if model_file_path_from_settings and model_file_path_from_settings != "backend/models/movenet_lightning.tflite" and model_file_path_from_settings != "models/posenet_mobilenet_v1_100_257x257_multi_kpt_stripped.tflite":  # Check not default placeholder
        print(f"INFO: POSE_ESTIMATION_MODEL_PATH is set to: '{model_file_path_from_settings}'")
        pose_estimator_instance = PoseEstimator(model_file_path_from_settings)
    else:
        # Attempt to load with the new default if placeholder was used
        new_default_path = "backend/models/movenet_lightning.tflite"  # Consistent with README
        print(
            f"INFO: POSE_ESTIMATION_MODEL_PATH is using a default or placeholder. Attempting to load from '{new_default_path}' if it exists.")
        if os.path.exists(new_default_path):
            pose_estimator_instance = PoseEstimator(new_default_path)
        else:
            print(f"WARNING: Default model path '{new_default_path}' not found. CV Form Analysis will be limited.")
            print(f"  Please set POSE_ESTIMATION_MODEL_PATH in .env and ensure the model file exists.")
            print(
                f"  You can download a MoveNet TFLite model from TensorFlow Hub (e.g., search 'movenet singlepose lightning tflite').")

    if pose_estimator_instance and not pose_estimator_instance.interpreter:  # If PoseEstimator init failed
        pose_estimator_instance = None  # Ensure it's None so app knows it's not usable
else:
    print("INFO: Skipping PoseEstimator initialization as TFLite runtime is not available.")


def get_landmark(keypoints: np.ndarray, landmark_name: str) -> Optional[Tuple[float, float, float]]:
    idx = KEYPOINT_DICT.get(landmark_name)
    if idx is None or keypoints is None or not isinstance(keypoints, np.ndarray) or keypoints.ndim != 2 or \
            keypoints.shape[0] != NUM_KEYPOINTS or keypoints.shape[1] != 3:
        # print(f"Warning: Invalid keypoints array or landmark '{landmark_name}' not found.")
        return None
    y, x, score = keypoints[idx]
    if score < MIN_KEYPOINT_VISIBILITY_SCORE:
        return None
    return float(y), float(x), float(score)


def calculate_angle(p1_coords: Tuple[float, float], p2_vertex_coords: Tuple[float, float],
                    p3_coords: Tuple[float, float]) -> float:
    v21 = (p1_coords[0] - p2_vertex_coords[0], p1_coords[1] - p2_vertex_coords[1])
    v23 = (p3_coords[0] - p2_vertex_coords[0], p3_coords[1] - p2_vertex_coords[1])
    dot_product = v21[0] * v23[0] + v21[1] * v23[1]
    mag_v21 = math.sqrt(v21[0] ** 2 + v21[1] ** 2)
    mag_v23 = math.sqrt(v23[0] ** 2 + v23[1] ** 2)
    if mag_v21 * mag_v23 == 0: return 180.0

    cos_angle = np.clip(dot_product / (mag_v21 * mag_v23), -1.0, 1.0)
    angle_rad = math.acos(cos_angle)
    return math.degrees(angle_rad)


def analyze_squat_frame(keypoints: np.ndarray) -> Dict[str, Any]:
    feedback = []
    issues = 0
    angles = {}

    left_hip_kp = get_landmark(keypoints, 'left_hip')
    right_hip_kp = get_landmark(keypoints, 'right_hip')
    left_knee_kp = get_landmark(keypoints, 'left_knee')
    right_knee_kp = get_landmark(keypoints, 'right_knee')
    left_ankle_kp = get_landmark(keypoints, 'left_ankle')
    right_ankle_kp = get_landmark(keypoints, 'right_ankle')

    hip_kp = left_hip_kp if left_hip_kp else right_hip_kp
    knee_kp = left_knee_kp if left_knee_kp else right_knee_kp
    ankle_kp = left_ankle_kp if left_ankle_kp else right_ankle_kp

    if hip_kp and knee_kp and ankle_kp:
        knee_angle = calculate_angle((hip_kp[0], hip_kp[1]), (knee_kp[0], knee_kp[1]), (ankle_kp[0], ankle_kp[1]))
        angles['knee_angle'] = round(knee_angle, 1)
        if knee_angle < 90:
            feedback.append("Good squat depth (thighs parallel or below).")
        elif knee_angle < 110:
            feedback.append("Try to squat deeper; aim for thighs parallel to the ground.")
            issues += 1
        else:
            feedback.append("Squat depth is shallow. Focus on lowering hips further.")
            issues += 2

        # Check if knees go too far past toes (relative to hip-knee-ankle line) - very simplified.
        # A better check involves comparing x-coordinates if camera angle is known.
        # If ankle_kp[1] (x of ankle) is significantly less than knee_kp[1] (x of knee)
        # and hip_kp[1] is also less, it might indicate knees past toes.
        # This is highly dependent on view and not robust.
        # if knee_kp[1] > ankle_kp[1] + 0.05: # knee x > ankle x + threshold (assuming side view, facing right)
        #     feedback.append("Watch for knees extending too far past toes.")
        #     issues += 0.5

    else:
        feedback.append("Could not determine knee angle (hip, knee, or ankle not clearly visible).")
        issues += 1

    # Back straightness is hard to judge from 2D without torso keypoints (e.g. mid-spine)
    # or assuming a very specific camera angle. Shoulder-hip alignment with vertical could be a proxy.
    # For now, this is omitted for simplicity.

    form_score = max(0, 1.0 - issues * 0.2)  # Each major issue reduces score by 20%
    return {"feedback": feedback, "form_score_frame": form_score, "angles": angles}


def analyze_pushup_frame(keypoints: np.ndarray) -> Dict[str, Any]:
    feedback = []
    issues = 0
    angles = {}

    shoulder_kp = get_landmark(keypoints, 'left_shoulder') or get_landmark(keypoints, 'right_shoulder')
    elbow_kp = get_landmark(keypoints, 'left_elbow') or get_landmark(keypoints, 'right_elbow')
    wrist_kp = get_landmark(keypoints, 'left_wrist') or get_landmark(keypoints, 'right_wrist')
    hip_kp = get_landmark(keypoints, 'left_hip') or get_landmark(keypoints, 'right_hip')
    ankle_kp = get_landmark(keypoints, 'left_ankle') or get_landmark(keypoints, 'right_ankle')
    knee_kp = get_landmark(keypoints, 'left_knee') or get_landmark(keypoints, 'right_knee')

    end_body_point_kp = ankle_kp  # Assume full pushup
    if not end_body_point_kp and knee_kp:  # If ankles not visible, check for knee pushup
        end_body_point_kp = knee_kp

    if shoulder_kp and elbow_kp and wrist_kp:
        elbow_angle = calculate_angle((shoulder_kp[0], shoulder_kp[1]), (elbow_kp[0], elbow_kp[1]),
                                      (wrist_kp[0], wrist_kp[1]))
        angles['elbow_angle'] = round(elbow_angle, 1)
        # Assuming lower is better for push-up depth, meaning smaller elbow angle at bottom
        if elbow_angle < 95:  # Good depth if this is the bottom of the movement
            feedback.append("Good elbow flexion, likely good depth.")
        elif elbow_angle < 120 and elbow_kp[0] > shoulder_kp[0]:  # elbow y > shoulder y = body lowered
            feedback.append("Aim for more depth; elbows to at least 90 degrees.")
            issues += 1
        # If elbow_angle is large (e.g. > 150), it's likely top of pushup, which is fine.
    else:
        feedback.append("Could not determine elbow angle (shoulder, elbow, or wrist not clearly visible).")
        issues += 1

    if shoulder_kp and hip_kp and end_body_point_kp:
        # Angle shoulder-hip-end_body_point (ankle or knee)
        body_line_angle = calculate_angle((shoulder_kp[0], shoulder_kp[1]), (hip_kp[0], hip_kp[1]),
                                          (end_body_point_kp[0], end_body_point_kp[1]))
        angles['body_line_angle'] = round(body_line_angle, 1)
        if body_line_angle < 160:  # Significant deviation from straight
            feedback.append("Keep your body straighter from shoulders to ankles/knees. Avoid hip sag or pike.")
            issues += 1
        elif body_line_angle > 170:  # Good alignment
            feedback.append("Good straight body line maintained.")
    else:
        feedback.append("Could not determine body alignment (shoulder, hip, or ankle/knee not clearly visible).")
        issues += 1

    form_score = max(0, 1.0 - issues * 0.25)
    return {"feedback": feedback, "form_score_frame": form_score, "angles": angles}


def analyze_exercise_form_from_frames(
        video_frames_base64: List[str],
        exercise_type: str
) -> Dict[str, Any]:
    if not pose_estimator_instance or not pose_estimator_instance.interpreter:
        return {"error": "Pose estimation model not loaded or not configured properly. Cannot analyze form."}

    if not video_frames_base64:
        return {"error": "No video frames provided for analysis."}

    all_frame_feedback_msgs = []
    sum_form_score = 0.0
    frames_successfully_processed = 0
    aggregated_angles: Dict[str, List[float]] = {}

    for i, frame_b64 in enumerate(video_frames_base64):
        try:
            frame_bytes = base64.b64decode(frame_b64)
        except Exception as e:
            print(f"Warning: Could not decode base64 frame {i}: {e}")
            all_frame_feedback_msgs.append(f"Frame {i + 1}: Decoding error.")
            continue

        keypoints = pose_estimator_instance.run_inference(frame_bytes)

        if keypoints is None or not isinstance(keypoints, np.ndarray) or keypoints.ndim != 2 or keypoints.shape[
            0] != NUM_KEYPOINTS or keypoints.shape[1] != 3:
            all_frame_feedback_msgs.append(
                f"Frame {i + 1}: Could not get valid keypoints (shape: {keypoints.shape if isinstance(keypoints, np.ndarray) else 'None or invalid'}).")
            continue

        frames_successfully_processed += 1
        frame_analysis_result: Dict[str, Any] = {}

        exercise_type_lower = exercise_type.lower()
        if "squat" in exercise_type_lower:
            frame_analysis_result = analyze_squat_frame(keypoints)
        elif "push-up" in exercise_type_lower or "pushup" in exercise_type_lower:
            frame_analysis_result = analyze_pushup_frame(keypoints)
        # Add more exercises:
        # elif "lunge" in exercise_type_lower:
        #     frame_analysis_result = analyze_lunge_frame(keypoints)
        # elif "bicep curl" in exercise_type_lower or "curl" in exercise_type_lower:
        #     frame_analysis_result = analyze_bicep_curl_frame(keypoints)
        else:
            # If specific analysis not found, return a generic message for this frame or overall
            all_frame_feedback_msgs.append(
                f"Frame {i + 1}: Analysis for '{exercise_type}' not specifically implemented. Generic pose captured.")
            frame_analysis_result = {"feedback": ["Generic pose captured."], "form_score_frame": 0.5,
                                     "angles": {}}  # Neutral score

        frame_feedback_list = frame_analysis_result.get("feedback", [])
        if frame_feedback_list:
            all_frame_feedback_msgs.extend([f"Frame {i + 1}: {fb}" for fb in frame_feedback_list])
        sum_form_score += frame_analysis_result.get("form_score_frame", 0)

        current_frame_angles = frame_analysis_result.get("angles", {})
        for angle_name, angle_value in current_frame_angles.items():
            if angle_name not in aggregated_angles: aggregated_angles[angle_name] = []
            if isinstance(angle_value, (int, float)):  # Ensure it's a number
                aggregated_angles[angle_name].append(angle_value)

    if frames_successfully_processed == 0:
        final_error_msg = "No frames could be processed successfully for keypoint extraction."
        if all_frame_feedback_msgs:  # If there were decoding errors, include that info
            final_error_msg += " Check detailed messages. Common issues: invalid base64, empty frames."
        return {"error": final_error_msg, "detailed_frame_messages": all_frame_feedback_msgs}

    average_form_score_overall = sum_form_score / frames_successfully_processed

    unique_feedback_issues = set()
    positive_feedback_observed = False
    for msg_with_frame_num in all_frame_feedback_msgs:
        msg_core = msg_with_frame_num.split(": ", 1)[1] if ": " in msg_with_frame_num else msg_with_frame_num
        if "Good" in msg_core or "good" in msg_core:
            positive_feedback_observed = True
        elif "Could not determine" not in msg_core and "Decoding error" not in msg_core and "Generic pose captured" not in msg_core:
            unique_feedback_issues.add(msg_core)

    final_corrective_feedback = sorted(list(unique_feedback_issues))  # Sort for consistent order
    if not final_corrective_feedback and positive_feedback_observed and average_form_score_overall > 0.85:
        final_corrective_feedback.append("Overall good form detected!")
    elif not final_corrective_feedback and not positive_feedback_observed:
        final_corrective_feedback.append(
            "Analysis inconclusive or keypoints not consistently visible for detailed feedback.")
    elif not final_corrective_feedback and "Generic pose captured." in all_frame_feedback_msgs[
        0]:  # If only generic feedback
        final_corrective_feedback.append(
            f"Pose captured for {exercise_type}. Specific form cues for this exercise are not yet implemented.")

    key_metrics_summary = {}
    for angle_name, angle_values_list in aggregated_angles.items():
        if angle_values_list:  # Ensure list is not empty
            key_metrics_summary[f"{angle_name}_min"] = round(min(angle_values_list), 1)
            key_metrics_summary[f"{angle_name}_max"] = round(max(angle_values_list), 1)
            key_metrics_summary[f"{angle_name}_avg"] = round(sum(angle_values_list) / len(angle_values_list), 1)

    return {
        "exercise_type_analyzed": exercise_type,
        "frames_input": len(video_frames_base64),
        "frames_processed_successfully": frames_successfully_processed,
        "overall_form_score": round(average_form_score_overall, 2),
        "corrective_feedback": final_corrective_feedback,
        "key_metrics_summary": key_metrics_summary if key_metrics_summary else None,
        # "detailed_frame_messages": all_frame_feedback_msgs # Enable for debugging
    }