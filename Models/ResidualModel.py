#!/usr/bin/python3
# -*- coding: utf-8 -*-

__author__ = 'unknown'
__email__ = 'unknown@unknown.com.br'
__version__ = '{1}.{0}.{0}'
__initial_data__ = '2024/07/17'
__last_update__ = '2024/07/17'
__credits__ = ['unknown']

import logging

try:
    import os
    import sys
    import glob
    import numpy
    import librosa
    import tensorflow

    from tqdm import tqdm
    import librosa.display
    from tensorflow.keras import Model
    from sklearn.utils import resample
    from tensorflow.keras.layers import Conv2D
    from tensorflow.keras.layers import Flatten
    from tensorflow.keras.layers import Dense
    from tensorflow.keras.layers import Input
    from tensorflow.keras.layers import Dropout
    from tensorflow.keras.layers import Concatenate
    from tensorflow.keras.layers import MaxPooling2D
    from sklearn.model_selection import StratifiedKFold
    from sklearn.model_selection import train_test_split

    from Modules.Evaluation.MetricsCalculator import MetricsCalculator

except ImportError as error:

    print(error)
    print("1. Install requirements:")
    print("  pip3 install --upgrade pip")
    print("  pip3 install -r requirements.txt ")
    print()
    sys.exit(-1)

# Default values
DEFAULT_SAMPLE_RATE = 8000
DEFAULT_HOP_LENGTH = 256
DEFAULT_SIZE_BATCH = 32
DEFAULT_WINDOW_SIZE_FACTOR = 40
DEFAULT_NUMBER_FILTERS_SPECTROGRAM = 512
DEFAULT_FILTERS_PER_BLOCK = [16, 32, 64, 96]
DEFAULT_FILE_EXTENSION = "*.wav"
DEFAULT_DROPOUT_RATE = 0.1
DEFAULT_NUMBER_LAYERS = 4
DEFAULT_OPTIMIZER_FUNCTION = 'adam'
DEFAULT_OVERLAP = 2
DEFAULT_LOSS_FUNCTION = 'sparse_categorical_crossentropy'
DEFAULT_DECIBEL_SCALE_FACTOR = 80
DEFAULT_CONVOLUTIONAL_PADDING = 'same'
DEFAULT_INPUT_DIMENSION = (513, 40, 1)
DEFAULT_INTERMEDIARY_ACTIVATION = 'relu'
DEFAULT_LAST_LAYER_ACTIVATION = 'softmax'
DEFAULT_NUMBER_CLASSES = 4
DEFAULT_SIZE_POOLING = (2, 2)
DEFAULT_WINDOW_SIZE = 1024
DEFAULT_NUMBER_EPOCHS = 10
DEFAULT_NUMBER_SPLITS = 5
DEFAULT_SIZE_CONVOLUTIONAL_FILTERS = (3, 3)


class ResidualModel(MetricsCalculator):
    """
    A class for creating and training a Convolutional Neural Network (CNN) with residual connections.

    Methods
    -------
    build_model()
        Constructs the CNN model with residual connections.
    windows(data, window_size, overlap)
        Generates windowed segments of the input data.
    load_data(sub_directories: str = None, file_extension: str = None) -> tuple
        Loads audio data, extracts features, and prepares labels.
    compile_model() -> None
        Compiles the CNN model with the specified loss function and optimizer.
    train(train_data_dir: str, number_epochs: int = None, batch_size: int = None,
          number_splits: int = None) -> tuple
        Trains the model using cross-validation and returns the mean metrics and training history.
    """

    def __init__(self, sample_rate=DEFAULT_SAMPLE_RATE,
                 hop_length=DEFAULT_HOP_LENGTH,
                 window_size_factor=DEFAULT_WINDOW_SIZE_FACTOR,
                 number_filters_spectrogram=DEFAULT_NUMBER_FILTERS_SPECTROGRAM,
                 number_layers=DEFAULT_NUMBER_LAYERS,
                 input_dimension=DEFAULT_INPUT_DIMENSION,
                 overlap=DEFAULT_OVERLAP,
                 convolutional_padding=DEFAULT_CONVOLUTIONAL_PADDING,
                 intermediary_activation=DEFAULT_INTERMEDIARY_ACTIVATION,
                 last_layer_activation=DEFAULT_LAST_LAYER_ACTIVATION,
                 number_classes=DEFAULT_NUMBER_CLASSES,
                 size_convolutional_filters=DEFAULT_SIZE_CONVOLUTIONAL_FILTERS,
                 size_pooling=DEFAULT_SIZE_POOLING,
                 window_size_fft=DEFAULT_WINDOW_SIZE,
                 decibel_scale_factor=DEFAULT_DECIBEL_SCALE_FACTOR,
                 filters_per_block=None,
                 size_batch=DEFAULT_SIZE_BATCH,
                 number_splits=DEFAULT_NUMBER_SPLITS,
                 number_epochs=DEFAULT_NUMBER_EPOCHS,
                 loss_function=DEFAULT_LOSS_FUNCTION,
                 optimizer_function=DEFAULT_OPTIMIZER_FUNCTION,
                 dropout_rate=DEFAULT_DROPOUT_RATE,
                 file_extension=DEFAULT_FILE_EXTENSION):

        """
        Initializes the ResidualModel with the given parameters.

        Parameters
        ----------
        sample_rate: The sample rate of the audio data.
        hop_length: The hop length for the spectrogram.
        window_size_factor: The factor by which the window size is multiplied.
        number_filters_spectrogram: The number of filters in the spectrogram.
        number_layers: The number of layers in the model.
        input_dimension: The shape of the input data.
        overlap: The overlap between consecutive windows.
        convolutional_padding: The padding type for convolutional layers.
        intermediary_activation: The activation function for intermediate layers.
        last_layer_activation: The activation function for the last layer.
        number_classes: The number of output classes.
        size_convolutional_filters: The size of the convolutional filters.
        size_pooling: The size of the pooling layers.
        window_size_fft: The size of the FFT window.
        decibel_scale_factor: The scale factor for converting power spectrogram to decibels.
        filters_per_block: List specifying the number of filters for each convolutional block.
        size_batch: The batch size for training.
        number_splits: The number of splits for cross-validation.
        number_epochs: The number of epochs for training.
        loss_function: The loss function used for training the model.
        optimizer_function: The optimizer function used for training the model.
        dropout_rate: The dropout rate used in the model.
        file_extension: The file extension for audio files.
        """

        if filters_per_block is None:
            filters_per_block = DEFAULT_FILTERS_PER_BLOCK

        self.model_name = "ResidualModel"
        self.neural_network_model = None
        self.sample_rate = sample_rate
        self.size_batch = size_batch
        self.number_splits = number_splits
        self.loss_function = loss_function
        self.size_pooling = size_pooling
        self.filters_per_block = filters_per_block
        self.hop_length = hop_length
        self.decibel_scale_factor = decibel_scale_factor
        self.window_size_fft = window_size_fft
        self.window_size_factor = window_size_factor
        self.window_size = hop_length * (self.window_size_factor - 1)
        self.number_filters_spectrogram = number_filters_spectrogram
        self.number_layers = number_layers
        self.input_shape = input_dimension
        self.overlap = overlap
        self.number_epochs = number_epochs
        self.optimizer_function = optimizer_function
        self.dropout_rate = dropout_rate
        self.file_extension = file_extension
        self.size_convolutional_filters = size_convolutional_filters
        self.number_classes = number_classes
        self.last_layer_activation = last_layer_activation
        self.convolutional_padding = convolutional_padding
        self.intermediary_activation = intermediary_activation

    def build_model(self):
        """
        Constructs a Convolutional Neural Network (CNN) with residual connections.

        This method creates a CNN model architecture by stacking convolutional layers with residual connections,
        followed by pooling and dropout layers.

        Returns
        -------
        keras.Model
            The compiled Convolutional model.
        """
        inputs = Input(shape=self.input_shape)
        neural_network_flow = inputs

        for number_filters in self.filters_per_block:
            residual_flow = neural_network_flow

            # Apply convolutional layers
            neural_network_flow = Conv2D(number_filters, self.size_convolutional_filters,
                                         activation=self.intermediary_activation,
                                         padding=self.convolutional_padding)(neural_network_flow)
            neural_network_flow = Conv2D(number_filters, self.size_convolutional_filters,
                                         activation=self.intermediary_activation,
                                         padding=self.convolutional_padding)(neural_network_flow)

            # Add residual connection
            neural_network_flow = Concatenate()([neural_network_flow, residual_flow])

            # Apply pooling and dropout
            neural_network_flow = MaxPooling2D(self.size_pooling)(neural_network_flow)
            neural_network_flow = Dropout(self.dropout_rate)(neural_network_flow)

        # Flatten and apply dense layer
        neural_network_flow = Flatten()(neural_network_flow)
        neural_network_flow = Dense(self.number_classes, activation=self.last_layer_activation)(neural_network_flow)

        # Define the model
        self.neural_network_model = Model(inputs=inputs, outputs=neural_network_flow, name=self.model_name)

    @staticmethod
    def windows(data, window_size, overlap):
        """
        Generates windowed segments of the input data.

        Parameters
        ----------
        data : numpy.ndarray
            The input data array.
        window_size : int
            The size of each window.
        overlap : int
            The overlap between consecutive windows.

        Yields
        ------
        tuple
            Start and end indices of each window.
        """
        start = 0
        while start < len(data):
            yield start, start + window_size
            start += (window_size // overlap)

    def load_data(self, sub_directories: str = None, file_extension: str = None) -> tuple:
        """
        Loads audio data, extracts features, and prepares labels.

        This method reads audio files from the specified directories, extracts spectrogram features,
        and prepares the corresponding labels.

        Parameters
        ----------
        sub_directories : str
            Path to the parent directory containing subdirectories with audio files.
        file_extension : str, optional
            The file extension for audio files. If not provided, the default from the initialization is used.

        Returns
        -------
        tuple
            A tuple containing:
            - numpy.ndarray: Feature array (spectrograms).
            - numpy.ndarray: Label array (class labels).
        """
        logging.info("Starting data loading process.")

        list_spectrogram, list_labels, list_class_path = [], [], []
        file_extension = file_extension or self.file_extension

        # Collect class paths
        logging.info(f"Listing subdirectories in {sub_directories}")
        for class_dir in os.listdir(sub_directories):
            class_path = os.path.join(sub_directories, class_dir)
            list_class_path.append(class_path)

        # Process each subdirectory
        for _, sub_directory in enumerate(list_class_path):
            logging.info(f"Processing directory: {sub_directory}")

            for file_name in tqdm(glob.glob(os.path.join(sub_directory, file_extension))):

                # Load the audio signal
                signal, _ = librosa.load(file_name, sr=self.sample_rate)
                label = file_name.split('/')[-2].split('_')[0]  # Extract label from the file path

                # Segment the audio into windows
                for (start, end) in self.windows(signal, self.window_size, self.overlap):

                    if len(signal[start:end]) == self.window_size:
                        signal_segment = signal[start:end]

                        # Generate a mel spectrogram
                        spectrogram = librosa.feature.melspectrogram(y=signal_segment,
                                                                     n_mels=self.number_filters_spectrogram,
                                                                     sr=self.sample_rate,
                                                                     n_fft=self.window_size_fft,
                                                                     hop_length=self.hop_length)

                        # Convert the spectrogram to decibel scale
                        spectrogram_decibel_scale = librosa.power_to_db(spectrogram, ref=numpy.max)
                        spectrogram_decibel_scale = (spectrogram_decibel_scale / self.decibel_scale_factor) + 1
                        list_spectrogram.append(spectrogram_decibel_scale)
                        list_labels.append(label)

        # Convert lists to arrays
        array_features = numpy.array(list_spectrogram).reshape(len(list_spectrogram),
                                                            self.number_filters_spectrogram,
                                                            self.window_size_factor, 1)
        array_labels = numpy.array(list_labels, dtype=numpy.int32)

        # Adjust array shape for additional dimensions
        logging.info("Reshaping feature array.")
        new_shape = list(array_features.shape)
        new_shape[1] += 1  # Adding an additional filter dimension
        new_array = numpy.zeros(new_shape)
        new_array[:, :self.number_filters_spectrogram, :, :] = array_features

        logging.info("Data loading complete.")
        return numpy.array(new_array, dtype=numpy.float32), array_labels

    def compile_and_train(self, train_data: tensorflow.Tensor, train_labels: tensorflow.Tensor, epochs: int,
                          batch_size: int, validation_data: tuple = None) -> tensorflow.keras.callbacks.History:
        """
        Compiles and trains the LSTM model on the provided training data.

        :param train_data: Tensor containing the training data.
        :param train_labels: Tensor containing the training labels.
        :param epochs: Number of training epochs.
        :param batch_size: Batch size for training.
        :param validation_data: Tuple containing validation data and labels (optional).
        :return: Training history containing metrics and loss values for each epoch.
        """
        self.neural_network_model.compile(optimizer=self.optimizer_function, loss=self.loss_function,
                                          metrics=['accuracy'])

        training_history = self.neural_network_model.fit(train_data, train_labels, epochs=epochs,
                                                         batch_size=batch_size,
                                                         validation_data=validation_data)
        return training_history

    def train(self, dataset_directory, number_epochs, batch_size, number_splits,
              loss, sample_rate, overlap, number_classes, arguments) -> tuple:
        """
        Trains the model using cross-validation.

        Parameters
        ----------
        dataset_directory : str
            Directory containing the training data.
        number_epochs : int, optional
            Number of training epochs.
        batch_size : int, optional
            Batch size for training.
        number_splits : int, optional
            Number of splits for cross-validation.

        Returns
        -------
        tuple
            A tuple containing the mean metrics, the training history, the mean confusion matrix,
            and the predicted probabilities along with the ground truth labels.
        """
        # Use default values if not provided
        self.number_epochs = number_epochs or self.number_epochs
        self.number_splits = number_splits or self.number_splits
        self.size_batch = batch_size or self.size_batch
        self.loss_function = loss or self.loss_function
        self.sample_rate = sample_rate or self.sample_rate
        self.overlap = overlap or self.overlap
        self.number_classes = number_classes or self.number_classes

        self.size_pooling = arguments.residual_size_pooling
        self.filters_per_block = arguments.residual_filters_per_block
        self.hop_length = arguments.residual_hop_length
        self.decibel_scale_factor = arguments.residual_decibel_scale_factor
        self.window_size_factor = arguments.residual_window_size_factor
        self.window_size = self.hop_length * (self.window_size_factor - 1)
        self.number_filters_spectrogram = arguments.residual_number_filters_spectrogram
        self.number_layers = arguments.residual_number_layers
        self.overlap = arguments.residual_overlap
        self.dropout_rate = arguments.residual_dropout_rate
        self.size_convolutional_filters = arguments.residual_size_convolutional_filters
        self.last_layer_activation = arguments.residual_last_layer_activation
        self.convolutional_padding = arguments.residual_convolutional_padding
        self.intermediary_activation = arguments.residual_intermediary_activation





        history_model = None
        features, labels = self.load_data(dataset_directory)
        metrics_list, confusion_matriz_list = [], []
        labels = numpy.array(labels).astype(float)

        # Split data into train/val and test sets
        features_train_val, features_test, labels_train_val, labels_test = train_test_split(
            features, labels, test_size=0.2, stratify=labels, random_state=42
        )

        # Function to balance the classes by resampling
        def balance_classes(features, labels):
            unique_classes = numpy.unique(labels)
            max_samples = max([sum(labels == c) for c in unique_classes])

            balanced_features = []
            balanced_labels = []

            for c in unique_classes:
                features_class = features[labels == c]
                labels_class = labels[labels == c]

                features_class_resampled, labels_class_resampled = resample(
                    features_class, labels_class,
                    replace=True,
                    n_samples=max_samples,
                    random_state=0
                )

                balanced_features.append(features_class_resampled)
                balanced_labels.append(labels_class_resampled)

            balanced_features = numpy.vstack(balanced_features)
            balanced_labels = numpy.hstack(balanced_labels)

            return balanced_features, balanced_labels

        # Balance training/validation set
        features_train_val, labels_train_val = balance_classes(features_train_val, labels_train_val)

        # Stratified k-fold cross-validation on the training/validation set
        instance_k_fold = StratifiedKFold(n_splits=self.number_splits, shuffle=True, random_state=42)
        probabilities_list = []
        real_labels_list = []

        for train_indexes, val_indexes in instance_k_fold.split(features_train_val, labels_train_val):

            features_train, features_val = features_train_val[train_indexes], features_train_val[val_indexes]
            labels_train, labels_val = labels_train_val[train_indexes], labels_train_val[val_indexes]

            # Balance the training set for this fold
            features_train, labels_train = balance_classes(features_train, labels_train)

            self.build_model()
            self.neural_network_model.summary()

            history_model = self.compile_and_train(features_train, labels_train, epochs=self.number_epochs,
                                                   batch_size=self.size_batch,
                                                   validation_data=(features_val, labels_val))

            model_predictions = self.neural_network_model.predict(features_val)
            predicted_labels = numpy.argmax(model_predictions, axis=1)

            probabilities_list.append(model_predictions)
            real_labels_list.append(labels_val)

            # Calculate and store the metrics for this fold
            metrics, confusion_matrix = self.calculate_metrics(predicted_labels, labels_val, predicted_labels)
            metrics_list.append(metrics)
            confusion_matriz_list.append(confusion_matrix)

        # Calculate mean metrics across all folds
        mean_metrics = {
            'model_name': self.model_name,
            'Acc.': {'value': numpy.mean([metric['Accuracy'] for metric in metrics_list]),
                     'std': numpy.std([metric['Accuracy'] for metric in metrics_list])},
            'Prec.': {'value': numpy.mean([metric['Precision'] for metric in metrics_list]),
                      'std': numpy.std([metric['Precision'] for metric in metrics_list])},
            'Rec.': {'value': numpy.mean([metric['Recall'] for metric in metrics_list]),
                     'std': numpy.std([metric['Recall'] for metric in metrics_list])},
            'F1.': {'value': numpy.mean([metric['F1-Score'] for metric in metrics_list]),
                    'std': numpy.std([metric['F1-Score'] for metric in metrics_list])},
        }

        probabilities_predicted = {
            'model_name': self.model_name,
            'predicted': numpy.concatenate(probabilities_list),
            'ground_truth': numpy.concatenate(real_labels_list)
        }

        confusion_matrix_array = numpy.array(confusion_matriz_list)
        mean_confusion_matrix = numpy.mean(confusion_matrix_array, axis=0)
        mean_confusion_matrix = numpy.round(mean_confusion_matrix).astype(numpy.int32).tolist()

        mean_confusion_matrices = {
            "confusion_matrix": mean_confusion_matrix,
            "class_names": ['Class {}'.format(i) for i in range(self.number_classes)],
            "title": self.model_name
        }

        return (mean_metrics, {"Name": self.model_name, "History": history_model.history}, mean_confusion_matrices,
                probabilities_predicted)


def get_residual_model_args(parser):

    parser.add_argument('--residual_hop_length', type=int,
                        default=DEFAULT_HOP_LENGTH, help='Hop length for STFT')

    parser.add_argument('--residual_window_size_factor', type=int,
                        default=DEFAULT_WINDOW_SIZE_FACTOR, help='Factor applied to FFT window size')

    parser.add_argument('--residual_number_filters_spectrogram', type=int,
                        default=DEFAULT_NUMBER_FILTERS_SPECTROGRAM, help='Number of filters for spectrogram generation')

    parser.add_argument('--residual_filters_per_block',
                        default=DEFAULT_FILTERS_PER_BLOCK, help='Number of filters in each convolutional block')

    parser.add_argument('--residual_dropout_rate', type=float,
                        default=DEFAULT_DROPOUT_RATE, help='Dropout rate in the network')

    parser.add_argument('--residual_number_layers', type=int,
                        default=DEFAULT_NUMBER_LAYERS, help='Number of convolutional layers')

    parser.add_argument('--residual_overlap', type=int,
                        default=DEFAULT_OVERLAP, help='Overlap between patches in the spectrogram')

    parser.add_argument('--residual_decibel_scale_factor', type=float,
                        default=DEFAULT_DECIBEL_SCALE_FACTOR, help='Scale factor for converting to decibels')

    parser.add_argument('--residual_convolutional_padding', type=str,
                        default=DEFAULT_CONVOLUTIONAL_PADDING, help='Padding type for convolutional layers')

    parser.add_argument('--residual_intermediary_activation', type=str,
                        default=DEFAULT_INTERMEDIARY_ACTIVATION, help='Activation function for intermediary layers')

    parser.add_argument('--residual_last_layer_activation', type=str,
                        default=DEFAULT_LAST_LAYER_ACTIVATION, help='Activation function for the last layer')

    parser.add_argument('--residual_size_pooling', type=tuple,
                        default=DEFAULT_SIZE_POOLING, help='Size of the pooling layers')

    parser.add_argument('--residual_window_size', type=int,
                        default=DEFAULT_WINDOW_SIZE, help='Size of the FFT window')

    parser.add_argument('--residual_size_convolutional_filters', type=tuple,
                        default=DEFAULT_SIZE_CONVOLUTIONAL_FILTERS, help='Size of the convolutional filters')

    return parser