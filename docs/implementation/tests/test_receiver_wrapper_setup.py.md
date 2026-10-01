Source: [tests/test_receiver_wrapper_setup.py](../../../tests/test_receiver_wrapper_setup.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

Four SDK43 targets cover L1–L3/L8: V2 file loading with mixed-profile refusal; one installed receiver serving two independently signed graph contexts with exact health-result correlation; new-host reconstruction and preserved application lifespan/routes; both stdlib server classes serving the same receiver contract with owned listener cleanup. Core prerequisites are exercised before SDK setup.

Expected initial red is a fixed SDK wrapper rejection of valid successor material, translated to an explicit assertion. Negative cases behind successful setup receive no independent red credit before reached. Passing these tests would prove SDK receiving/lifecycle behavior, not current graph permission, provider adoption, physical process continuity or real deployment advancement. The unchanged ordinary Docker gate owns execution; no test was executed during authoring.
