import joblib, glob
for f in glob.glob('newapp/models/*scaler.joblib'):
    print('===', f)
    scaler = joblib.load(f)
    attrs = [a for a in dir(scaler) if not a.startswith('_')]
    print('scaler class:', scaler.__class__)
    if hasattr(scaler,'feature_range'):
        print('feature_range:', scaler.feature_range)
    if hasattr(scaler,'n_features_in_'):
        print('n_features_in_:', scaler.n_features_in_)
    if hasattr(scaler,'data_min_'):
        print('data_min_ shape:', scaler.data_min_.shape)
    if hasattr(scaler,'data_max_'):
        print('data_max_ shape:', scaler.data_max_.shape)
