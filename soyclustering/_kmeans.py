import numpy as np
import scipy.sparse as sp
import warnings

from sklearn.metrics.pairwise import cosine_distances
from sklearn.utils import check_random_state
from sklearn.utils.extmath import stable_cumsum
from sklearn.utils import check_array
from sklearn.utils import as_float_array
from sklearn.utils.sparsefuncs_fast import assign_rows_csr


class SphericalKMeans:
    """Spherical k-Means clustering
    
    Parameters
    ----------
    n_clusters : int, optional, default: 8
        The number of clusters to form as well as the number of
        centroids to generate.
    init : {'k-means++', 'random' or an ndarray}
        Method for initialization, defaults to 'k-means++':
        'k-means++' : selects initial cluster centers for k-mean
        clustering in a smart way to speed up convergence. See section
        Notes in k_init for more details.
        'random': choose k observations (rows) at random from data for
        the initial centroids.
        If an ndarray is passed, it should be of shape (n_clusters, n_features)
        and gives the initial centers.    
    max_iter : int, default: 10
        Maximum number of iterations of the k-means algorithm for a
        single run. 
        It does not need large number. k-means algorithms converge fast.
    tol : float, default: 1e-4
        Relative tolerance with regards to inertia to declare convergence
    verbose : int, default 0
        Verbosity mode.
    random_state : int, RandomState instance or None, optional, default: None
        If int, random_state is the seed used by the random number generator;
        If RandomState instance, random_state is the random number generator;
        If None, the random number generator is the RandomState instance used
        by `np.random`.
    n_jobs : int
        To be implemented
    algorithm : str, default None
        Computation algorithm. 

    Attributes
    ----------
    cluster_centers_ : array, [n_clusters, n_features]
        Coordinates of cluster centers
    labels_ :
        Labels of each point
    inertia_ : float
        Sum of squared distances of samples to their closest cluster center.
    
    Examples
    --------
    >>> from soyclustering import SphericalKMeans
    >>> from scipy.io import mmread
    >>> x = mmread(mm_file).tocsr()
    >>> spherical_kmeans = SphericalKMeans(n_clusters=100, random_state=0)
    >>> labels = spherical_kmeans.fit_predict(X)
    >>> spherical_kmeans.cluster_centers_
    
    See also
    --------
    To be described. 

    Notes
    ------
    The k-means problem is solved using Lloyd's algorithm.
    The average complexity is given by O(k n T), were n is the number of
    samples and T is the number of iteration.
    In practice, the k-means algorithm is very fast (one of the fastest
    clustering algorithms available), but it falls in local minima. 
    However, the probability of facing local minima is low if we use
    enough large k for document clustering. 
    """
    
    def __init__(self, n_clusters=8, init='kmeans++', max_iter=10, 
                 tol=0.0001, verbose=0, random_state=None, n_jobs=1,
                 algorithm=None
                ):
        
        self.n_clusters = n_clusters
        self.init = init
        self.max_iter = max_iter
        self.tol = tol
        self.verbose = verbose
        self.random_state = random_state
        self.n_jobs = n_jobs
        self.algorithm = algorithm
    
    def _check_fit_data(self, X):
        """Verify that the number of samples given is larger than k
        Verify input data x is sparse matrix
        """
        X = check_array(X, accept_sparse='csr', dtype=[np.float64, np.float32])
        if X.shape[0] < self.n_clusters:
            raise ValueError("n_samples=%d should be >= n_clusters=%d" % (
                X.shape[0], self.n_clusters))
        if not sp.issparse(X):
            raise ValueError("Input must be instance of scipy.sparse.csr_matrix")
        return X
    
    def fit(self, X, y=None):
        """Compute k-means clustering.
        Parameters
        ----------
        X : array-like or sparse matrix, shape=(n_samples, n_features)
            Training instances to cluster.
        y : Ignored
        """
        random_state = check_random_state(self.random_state)
        X = self._check_fit_data(X)
        
        self.cluster_centers_, self.labels_, self.inertia_, = \
            k_means(
                X, n_clusters=self.n_clusters, init=self.init,
                max_iter=self.max_iter, verbose=self.verbose,
                tol=self.tol, random_state=random_state,
                n_jobs=self.n_jobs, algorithm=self.algorithm
            )
        return self
    
    def fit_predict(self, X, y=None):
        """Compute cluster centers and predict cluster index for each sample.
        
        Convenience method; equivalent to calling fit(X) followed by
        predict(X).
        
        Parameters
        ----------
        X : sparse matrix, shape = [n_samples, n_features]
            New data to transform.
        y : Ignored
        
        Returns
        -------
        labels : array, shape [n_samples,]
            Index of the cluster each sample belongs to.
        """
        return self.fit(X).labels_
    
    def transform(self, X):
        """Transform X to a cluster-distance space.
        In the new space, each dimension is the distance to the cluster
        centers.  Note that even if X is sparse, the array returned by
        `transform` will typically be dense.
        Parameters
        ----------
        X : sparse matrix, shape = [n_samples, n_features]
            New data to transform.
        Returns
        -------
        X_new : array, shape [n_samples, k]
            X transformed in the new space.
        """
        check_is_fitted(self, 'cluster_centers_')

        X = self._check_test_data(X)
        return self._transform(X)
    
    def _transform(self, X):
        """guts of transform method; no input validation"""
        return cosine_distances(X, self.cluster_centers_)

def _tolerance(X, tol):
    """Modified.
    The number of points which are re-assigned to other cluster. 
    """
    return max(1, int(X.shape[0] * tol))

def k_means(X, n_clusters, init='random', max_iter=10,
            verbose=False, tol=1e-4, random_state=None,
            n_jobs=1, algorithm=None
           ):

    random_state = check_random_state(random_state)

    if max_iter <= 0:
        raise ValueError('Number of iterations should be a positive number,'
                         ' got %d instead' % max_iter)

    X = as_float_array(X)
    tol = _tolerance(X, tol)
    
    # Validate init

    labels, inertia, centers = None, None, None
    
    # For a single thread, run a k-means once
    centers, labels, inertia, n_iter_ = kmeans_single(
        X, n_clusters, max_iter=max_iter, init=init, verbose=verbose,
        tol=tol, random_state=random_state, algorithm=algorithm)

    # parallelisation of k-means runs
    # TODO
    
    return centers, labels, inertia

def initialize(X, n_clusters, init, random_state):
    n_samples = X.shape[0]
    
    # Random selection
    if isinstance(init, str) and init == 'random':
        seeds = random_state.permutation(n_samples)[:k]
        centers = X[seeds]
    # Customized initial centroids
    elif hasattr(init, '__array__'):
        centers = np.array(init, dtype=X.dtype)
        if centers.shape[0] != n_clusters:
            raise ValueError('the number of customized initial points ' 
                             'should be same with n_clusters parameter'
                            )
    elif isinstance(init, str) and init == 'kmeans++':
        centers = _k_init(X, n_clusters, random_state)        
    # Sophisticated initialization 
    # TODO
    else:
        raise ValueError('the init parameter for spherical k-means should be '
                         'random or ndarray or '
                        )
    return centers

def _k_init(X, n_clusters, random_state):
    """Init n_clusters seeds according to k-means++
    It modified for Spherical k-means 
    
    Parameters
    -----------
    X : sparse matrix, shape (n_samples, n_features)        
    n_clusters : integer
        The number of seeds to choose
    random_state : numpy.RandomState
        The generator used to initialize the centers.

    Notes
    -----
    Selects initial cluster centers for k-mean clustering in a smart way
    to speed up convergence. see: Arthur, D. and Vassilvitskii, S.
    "k-means++: the advantages of careful seeding". ACM-SIAM symposium
    on Discrete algorithms. 2007
    Version ported from http://www.stanford.edu/~darthur/kMeansppTest.zip,
    which is the implementation used in the aforementioned paper.
    """
    
    n_samples, n_features = X.shape

    centers = np.empty((n_clusters, n_features), dtype=X.dtype)

    # Set the number of local seeding trials if none is given
    # This is what Arthur/Vassilvitskii tried, but did not report
    # specific results for other than mentioning in the conclusion
    # that it helped.
    n_local_trials = 2 + int(np.log(n_clusters))
        
    # Pick first center randomly
    center_id = random_state.randint(n_samples)
    centers[0] = X[center_id].toarray()

    # Initialize list of closest distances and calculate current potential
    closest_dist_sq = cosine_distances(centers[0, np.newaxis], X)[0] ** 2
    current_pot = closest_dist_sq.sum()

    # Pick the remaining n_clusters-1 points
    for c in range(1, n_clusters):
        # Choose center candidates by sampling with probability proportional
        # to the squared distance to the closest existing center
        rand_vals = random_state.random_sample() * current_pot
        candidate_ids = np.searchsorted(stable_cumsum(closest_dist_sq),
                                        rand_vals)

        centers[c] = X[candidate_ids].toarray()
        
        # Compute distances to center candidates
        closest_dist_sq = cosine_distances(X[candidate_ids,:], X)[0] ** 2
        current_pot = closest_dist_sq.sum()

    return centers

def kmeans_single(X, n_clusters, max_iter=10, init='kmeans++',
                  verbose=0, tol=1, random_state=None, algorithm=None):
    
    centers = initialize(X, n_clusters, init, random_state)
    if verbose:
        print('Initialization was completed')
    
    # Not developed optimized algorithm
    centers, labels, inertia, n_iter_ = _kmeans_single_banilla(
        X, n_clusters, centers, max_iter, verbose, tol)

    return centers, labels, inertia, n_iter_

def _kmeans_single_banilla(X, n_clusters, centers, max_iter, verbose, tol):
    
    n_samples = X.shape[0]
    labels_old = np.zeros((n_samples,), dtype=np.int)
    
    for n_iter_ in range(max_iter):
        
        dist = cosine_distances(X, centers)
        centers, labels = _assign(X, dist, n_clusters)
        inertia = dist.min(axis=1).sum()
        
        if n_iter_ == 0:
            n_diff = n_samples
        else:
            diff = np.where((labels_old - labels) != 0)[0]
            n_diff = len(diff)
        
        labels_old = labels
        
        # debug
        # n_samples_in_cluster_ = np.bincount(labels, minlength=n_clusters)
        # n_empty_clusters_ = np.where(n_samples_in_cluster_ == 0)[0].shape[0]
        # print('after assign, n_empty', n_empty_clusters_)
        
        if verbose:
            print('n_iter=%d, changed=%d, inertia=%.2f' % (n_iter_, n_diff, inertia))
        
        if n_diff <= tol:
            if verbose and (n_iter_ + 1 < max_iter):
                print('Early converged.')
            break
    
    n_iter_ += 1

    return centers, labels, inertia, n_iter_

def _assign(X, dist, n_clusters):
    
    n_featuers = X.shape[1]
    centers = np.zeros((n_clusters, n_featuers))
    
    labels = dist.argmin(axis=1)
    
    n_samples_in_cluster = np.bincount(labels, minlength=n_clusters)
    empty_clusters = np.where(n_samples_in_cluster == 0)[0]
    solo_clusters = np.where(n_samples_in_cluster == 1)[0]
    n_empty_clusters = empty_clusters.shape[0]
    
    data = X.data
    indices = X.indices
    indptr = X.indptr
    
    if n_empty_clusters > 0:
        #find points to reassign empty clusters to
        dist_copy = dist.copy()
        dist_copy.sort(axis=1)
        far_from_centers_ = dist_copy[:,-1].argsort()[::-1]
        far_from_centers = []
        for far in far_from_centers_:
            if not (far in empty_clusters) and not (far in solo_clusters):
                far_from_centers.append(far)
            if len(far_from_centers) == n_empty_clusters:
                break
        
        n_remain_empty_clusters = n_empty_clusters - len(far_from_centers)
        if n_remain_empty_clusters > 0:            
            warnings.warn('%d empty cluster exists' 
                % n_remain_empty_clusters, RuntimeWarning)
        
        # debug
        # print('empty', empty_clusters)
        
        for i in range(n_empty_clusters):
            centers[empty_clusters[i]] = X[far_from_centers[i]].toarray()
            n_samples_in_cluster[empty_clusters[i]] = 1
            labels[far_from_centers[i]] = empty_clusters[i]
            
        n_samples_in_cluster_ = np.bincount(labels, minlength=n_clusters)
        n_empty_clusters_ = np.where(n_samples_in_cluster_ == 0)[0].shape[0]
        
        # debug
        # print('empty {} --> {}'.format(n_empty_clusters, n_empty_clusters_))

    for i, curr_label in enumerate(labels):
        for ind in range(indptr[i], indptr[i + 1]):
            j = indices[ind]
            centers[curr_label, j] += data[ind]

    centers /= n_samples_in_cluster[:, np.newaxis]
    
    return centers, labels