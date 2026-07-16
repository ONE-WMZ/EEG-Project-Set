# Visual-Audio Interaction: An SSVEP Interaction Model Based on Perception-Decision Separation

---

## SSVEP BCI System

### Environment

```
Python = 3.10
    tkinter: GUI
    pylsl: LSL Scan|Connect|Get data 
    psychopy: Stimuli
    sklearn: CCA
    numpy: Data format
    scipy: Band filter
    screeninfo: get screen info
    multiprocessing: Manager process
    websockets: Realtime game
    cv2: Image process
```


### API Documentation
- Psychopy: https://www.psychopy.org/api/index.html#api
- CCA: https://scikit-learn.org/stable/modules/generated/sklearn.cross_decomposition.CCA.html
- LSL: https://docs.pypi.org/



### GUI Page
```
GUI:
    Person INfO
    EEG device
    Data Collect
    Analysis
    Realtime
```



### Data Format
```
Data_/
└── ID_i/ 
    ├── +.npy          
    ├── up.npy
    ├── down.npy
    ├── left.npy
    ├── right.npy
    ├── events.csv
    └── person_info.json
```




