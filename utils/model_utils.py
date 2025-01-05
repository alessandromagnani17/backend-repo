import cv2
import numpy as np
import tensorflow as tf
from typing import Tuple
from typing import Optional

class ModelManager:
    def __init__(self, model: tf.keras.Model):
        """
        Inizializza il gestore del modello con un'istanza del modello Keras.

        Args:
            model: Modello TensorFlow/Keras pre-addestrato.
        """
        self.model = model


    def preprocess_image(self, file) -> Tuple[np.ndarray, np.ndarray]:
        """
        Preprocessa l'immagine per l'input al modello.

        Args:
            file: File binario dell'immagine.

        Returns:
            Tuple[np.ndarray, np.ndarray]: 
                - Array preprocessato dell'immagine per l'input al modello.
                - Immagine RGB equalizzata per la visualizzazione o elaborazioni successive.
        """
        img = cv2.imdecode(np.frombuffer(file.read(), np.uint8), cv2.IMREAD_GRAYSCALE)
        equalized_img = cv2.equalizeHist(img)
        img_rgb = cv2.cvtColor(equalized_img, cv2.COLOR_GRAY2RGB)
        img_array = tf.keras.utils.img_to_array(img_rgb)
        img_array = np.expand_dims(img_array, axis=0)
        img_array = tf.keras.applications.resnet50.preprocess_input(img_array)
        return img_array, img_rgb


    def predict_class(self, img_array: np.ndarray) -> Tuple[int, float]:
        """
        Predice la classe dell'immagine.

        Args:
            img_array: Array preprocessato dell'immagine.

        Returns:
            Tuple[int, float]:
                - Classe predetta (indice della classe).
                - Fiducia associata alla classe predetta (valore float compreso tra 0 e 1).
        """
        predictions = self.model.predict(img_array)
        predicted_class = np.argmax(predictions[0])
        confidence = float(np.max(predictions[0]))
        return predicted_class, confidence


    def make_gradcam_heatmap(self, img_array: np.ndarray, last_conv_layer_name: str, pred_index: Optional[int] = None) -> np.ndarray:
        """
        Genera una heatmap Grad-CAM per l'immagine data.

        Args:
            img_array: Array preprocessato dell'immagine.
            last_conv_layer_name: Nome dell'ultimo strato convoluzionale nel modello.
            pred_index: Indice della classe per cui calcolare la heatmap. Se non fornito, utilizza la classe predetta.

        Returns:
            np.ndarray: Heatmap Grad-CAM normalizzata come array 2D.
        """
        resnet_model = self.model.get_layer('resnet50')
        last_conv_layer = resnet_model.get_layer(last_conv_layer_name)
        last_conv_layer_model = tf.keras.models.Model(resnet_model.input, last_conv_layer.output)
        
        classifier_input = tf.keras.layers.Input(shape=last_conv_layer.output.shape[1:])
        x = classifier_input
        for layer in self.model.layers[1:]:
            x = layer(x)
        classifier_model = tf.keras.models.Model(classifier_input, x)

        with tf.GradientTape() as tape:
            last_conv_layer_output = last_conv_layer_model(img_array)
            tape.watch(last_conv_layer_output)
            preds = classifier_model(last_conv_layer_output)
            if pred_index is None:
                pred_index = tf.argmax(preds[0])
            class_channel = preds[:, pred_index]

        grads = tape.gradient(class_channel, last_conv_layer_output)
        pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))
        last_conv_layer_output = last_conv_layer_output[0]
        heatmap = last_conv_layer_output @ pooled_grads[..., tf.newaxis]
        heatmap = tf.squeeze(heatmap)
        heatmap = tf.maximum(heatmap, 0) / tf.math.reduce_max(heatmap)
        return heatmap.numpy()


    def generate_gradcam(self, img_array: np.ndarray, predicted_class: int, img_rgb: np.ndarray) -> np.ndarray:
        """
        Genera l'immagine Grad-CAM sovrapponendo la heatmap sull'immagine originale.

        Args:
            img_array: Array preprocessato dell'immagine.
            predicted_class: Classe predetta utilizzata per generare la heatmap.
            img_rgb: Immagine RGB equalizzata.

        Returns:
            np.ndarray: Immagine Grad-CAM risultante con heatmap sovrapposta.
        """
        heatmap = self.make_gradcam_heatmap(img_array, "conv5_block3_out", pred_index=predicted_class)
        heatmap = np.uint8(255 * heatmap)
        heatmap = cv2.resize(heatmap, (img_rgb.shape[1], img_rgb.shape[0]))
        heatmap = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
        return cv2.addWeighted(img_rgb, 0.6, heatmap, 0.4, 0)
