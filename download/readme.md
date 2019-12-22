
Run the python script as following:

```
python smodel.py
```

Then the ROC curve will be displayed, and an AUC value will be computed.

<p align="center">
<img src="https://nmt4binaries.github.io/download/ROC.png" width="400">
</p>
 
**Please note that, because of SGD, each time when you re-train the model from scratch, the AUC value may be slightly different. The AUC value above is only computed according to the pre-trained weights provided here.**

------------------------------------------------

How to modify the backend of llvm to automatically output the bounderies of basic blocks.

Please subsitute AsmPrinter.cpp file provided here with the orginial one in llvm projects. (./lib/CodeGen/AsmPrinter/AsmPrinter.cpp)

LLVM provides two useful functions in MachineBasicBlock Class:

- getName () : Return the name of the corresponding LLVM basic block, or an empty string. 

- getFullName () : Return a formatted string to identify this block and its parent function. (Return a hopefully unique identifier for this block.)

We use getFullName() to generate an identifier for each basic block. Please refer to [llvm documents online](https://llvm.org/doxygen/classllvm_1_1MachineBasicBlock.html) to learn more details.

**Please note that the version of llvm we used in our implementation is 6.0.0. Considering the updates of llvm, different verisons of software may lead to unknown problems.**
