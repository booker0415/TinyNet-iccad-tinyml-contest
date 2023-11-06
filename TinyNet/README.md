# Folder Structure

- ./train_model_design/: the folder for the training design in Python

- ./deploy/: the folder which consists of the generated C source code

Our methods is based on **Machine Learning**, so there are **no model weight files**.



# Deploy and Test on MCU Development Board

The C source code from the STM32CubeMX platform has been generated already.

- Enter the folder **'MDK-ARM'** in the folder **'deploy'**

- Open the **'TESTMODEL.uvprojx'** in the folder **'MDK-ARM'**

- All Settings should have been configured properly, open **'Options for Target'**

  - Enter page **'Target'**, make sure that the **'ARM Compiler'** selection is **'Use default compiler version 6'** and **'Use MicroLIB'** is selected

  - Enter page **'C/C++ (AC6)'**, make sure that the **'Optimization'** selection is **'-Oz image size'** is selected

- **Rebuild the project**

- Connect the development board STM32F303K8T6 and **load the project**

-  Run validation.py and evaluate our methods on development board STM32F303K8T6



# The Training Design

Please find the code in folder 'train_model_design'

- train.py: This file is used for training and finding parameters, where factor and threshold are the parameters to be found, which determine the effectiveness and accuracy of the training.

- test.py: This file is used to test the performance of the algorithm using the corresponding parameters on the validation set. 
- ./data: This folder holds the training data set.
- ./data_indices: This folder holds the indice files.

