import re
import os
import glob
from datetime import datetime
import pandas as pd
from bs4 import BeautifulSoup
import numpy as np
from scipy.spatial import distance
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import silhouette_score
from collections import Counter

class TDOAMapExtractor:
    """Extract and visualize TDOA coordinates from multiple HTML files"""
    
    def __init__(self, directory_path='.'):
        self.directory_path = directory_path
        self.data = []
        self.skipped_files = []
    
    def check_heatmap_density(self, content, threshold=0.9, count_threshold=50):
        """
        Check if heatmapData has too many high density values (> 0.9)
        Returns True if file should be skipped
        """
        try:
            # Extract heatmapData array - updated pattern for OpenStreetMap format
            # Pattern harus match dengan format yang dihasilkan oleh create_html_file_osm.m
            heatmap_pattern = r"var\s+heatmapData\s*=\s*L\.heatLayer\(\s*\[(.*?)\]\s*,\s*\{"
            heatmap_match = re.search(heatmap_pattern, content, re.DOTALL)
            
            if not heatmap_match:
                # Try alternative pattern (untuk Google Maps atau format lain)
                heatmap_pattern_alt = r"heatmapData\s*=\s*\[(.*?)\]"
                heatmap_match = re.search(heatmap_pattern_alt, content, re.DOTALL)
                
                if not heatmap_match:
                    print(f"  [INFO] No heatmap data found in file")
                    return False  # No heatmap data, don't skip
            
            heatmap_data_str = heatmap_match.group(1)
            
            # Extract all density values (third value in each triplet)
            # Format dari MATLAB: [lat, long, density]
            # Improved pattern to handle scientific notation and various number formats
            density_pattern = r"\[\s*([+-]?\d+\.?\d*(?:[eE][+-]?\d+)?)\s*,\s*([+-]?\d+\.?\d*(?:[eE][+-]?\d+)?)\s*,\s*([+-]?\d+\.?\d*(?:[eE][+-]?\d+)?)\s*\]"
            density_matches = re.findall(density_pattern, heatmap_data_str)
            
            if not density_matches:
                print(f"  [INFO] No density values found in heatmap data")
                return False
            
            # Convert to float and count high density values (third element is density)
            densities = [float(match[2]) for match in density_matches]
            high_density_count = sum(1 for d in densities if d > threshold)
            
            total_points = len(densities)
            
            # Debug info for this file
            if total_points > 0:
                max_density = max(densities)
                min_density = min(densities)
                avg_density = sum(densities) / len(densities)
                print(f"  [HEATMAP] Points: {total_points}, High density (>{threshold}): {high_density_count}")
                print(f"  [DENSITY] Min: {min_density:.3f}, Max: {max_density:.3f}, Avg: {avg_density:.3f}")
            
            # Skip if more than count_threshold points have density > threshold
            should_skip = high_density_count > count_threshold
            
            if should_skip:
                print(f"  [SKIP] High density points: {high_density_count}/{total_points} (threshold: {count_threshold})")
            
            return should_skip
            
        except Exception as e:
            print(f"  [WARNING] Error checking heatmap density: {str(e)}")
            import traceback
            traceback.print_exc()
            return False  # Don't skip on error
    
    def extract_coordinates_from_html(self, html_file):
        """Extract Max Heat Point and AVG coordinates from single HTML file"""
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check heatmap density first
            if self.check_heatmap_density(content, threshold=0.9, count_threshold=50):
                self.skipped_files.append({
                    'filename': os.path.basename(html_file),
                    'reason': 'High density count > 50'
                })
                return None
            
            data = {
                'filename': os.path.basename(html_file),
                'max_heat_lat': None,
                'max_heat_long': None,
                'max_heat_value': None,
                'avg_lat': None,
                'avg_long': None,
                'avg_value': None,
                'target_lat': None,
                'target_long': None,
                'reference_lat': None,
                'reference_long': None,
                'rx1_lat': None,
                'rx1_long': None,
                'rx2_lat': None,
                'rx2_long': None,
                'rx3_lat': None,
                'rx3_long': None
            }
            
            # Extract Max Heat Point - multiple patterns to try
            patterns_max_heat = [
                r"var\s+maxHeatPoint\s*=\s*L\.marker\(\[\s*([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)\s*\]",
                r"maxHeatPoint.*?\[\s*([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)\s*\]",
            ]
            
            for pattern in patterns_max_heat:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    data['max_heat_lat'] = float(match.group(1))
                    data['max_heat_long'] = float(match.group(2))
                    
                    # Try to extract value from popup
                    value_pattern = r"maxHeatPoint.*?bindPopup.*?(\d+\.?\d*)\s*</b>"
                    value_match = re.search(value_pattern, content, re.DOTALL)
                    if value_match:
                        data['max_heat_value'] = float(value_match.group(1))
                    break
            
            # Extract AVG Point (marker_rx7)
            patterns_avg = [
                r"var\s+marker_rx7\s*=\s*L\.marker\(\[\s*([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)\s*\]",
                r"marker_rx7.*?\[\s*([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)\s*\]",
            ]
            
            for pattern in patterns_avg:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    data['avg_lat'] = float(match.group(1))
                    data['avg_long'] = float(match.group(2))
                    
                    # Try to extract value
                    value_pattern = r"marker_rx7.*?bindPopup.*?'AVG.*?(\d+\.?\d*)\s*</b>"
                    value_match = re.search(value_pattern, content, re.DOTALL)
                    if value_match:
                        data['avg_value'] = float(value_match.group(1))
                    break
            
            # Extract Target Point (marker_rx4)
            target_pattern = r"var\s+marker_rx4\s*=\s*L\.marker\(\[\s*([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)\s*\]"
            target_match = re.search(target_pattern, content)
            if target_match:
                data['target_lat'] = float(target_match.group(1))
                data['target_long'] = float(target_match.group(2))
            
            # Extract Reference Point (marker_rx5)
            ref_pattern = r"var\s+marker_rx5\s*=\s*L\.marker\(\[\s*([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)\s*\]"
            ref_match = re.search(ref_pattern, content)
            if ref_match:
                data['reference_lat'] = float(ref_match.group(1))
                data['reference_long'] = float(ref_match.group(2))
            
            # Extract Receiver positions
            rx_patterns = [
                (r"var\s+marker_rx1\s*=\s*L\.marker\(\[\s*([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)\s*\]", 'rx1'),
                (r"var\s+marker_rx2\s*=\s*L\.marker\(\[\s*([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)\s*\]", 'rx2'),
                (r"var\s+marker_rx3\s*=\s*L\.marker\(\[\s*([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)\s*\]", 'rx3'),
            ]
            
            for pattern, rx_name in rx_patterns:
                match = re.search(pattern, content)
                if match:
                    data[f'{rx_name}_lat'] = float(match.group(1))
                    data[f'{rx_name}_long'] = float(match.group(2))
            
            # Debug output for first file
            if not hasattr(self, '_debug_shown'):
                print(f"\n[DEBUG] First file analysis:")
                print(f"  Max Heat found: {data['max_heat_lat'] is not None}")
                print(f"  AVG found: {data['avg_lat'] is not None}")
                print(f"  Target found: {data['target_lat'] is not None}")
                print(f"  RX1 found: {data['rx1_lat'] is not None}")
                
                # Show sample of content for debugging
                if data['max_heat_lat'] is None:
                    print(f"\n  Searching for 'maxHeat' in file...")
                    max_heat_lines = [line for line in content.split('\n') if 'maxHeat' in line.lower()]
                    if max_heat_lines:
                        print(f"  Found lines with 'maxHeat': {len(max_heat_lines)}")
                        print(f"  Sample: {max_heat_lines[0][:200]}")
                    else:
                        print(f"  No 'maxHeat' found in file")
                
                if data['avg_lat'] is None:
                    print(f"\n  Searching for 'marker_rx7' or 'AVG' in file...")
                    avg_lines = [line for line in content.split('\n') if 'marker_rx7' in line or 'AVG' in line]
                    if avg_lines:
                        print(f"  Found lines: {len(avg_lines)}")
                        print(f"  Sample: {avg_lines[0][:200]}")
                
                self._debug_shown = True
            
            return data
            
        except Exception as e:
            print(f"Error processing {html_file}: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def process_multiple_files(self, pattern="121map*.html", start_minute=None, end_minute=None):
        """Process multiple HTML files based on pattern or time range"""
        
        # Method 1: Use glob pattern
        html_files = glob.glob(os.path.join(self.directory_path, pattern))
        
        # Method 2: Generate specific filenames based on time range
        if start_minute is not None and end_minute is not None:
            base_pattern = "121map_933_1031_2025_6_12_9_{}.dat_dphase_interp0_bw40_smooth0_osm.html"
            for minute in range(start_minute, end_minute + 1):
                filename = os.path.join(self.directory_path, base_pattern.format(minute))
                if os.path.exists(filename) and filename not in html_files:
                    html_files.append(filename)
        
        print(f"Found {len(html_files)} HTML files to process")
        
        if len(html_files) == 0:
            print(f"\nNo files found matching pattern: {pattern}")
            print(f"In directory: {self.directory_path}")
            return pd.DataFrame()
        
        processed_count = 0
        for html_file in sorted(html_files):
            print(f"Processing: {os.path.basename(html_file)}")
            data = self.extract_coordinates_from_html(html_file)
            if data:
                self.data.append(data)
                processed_count += 1
        
        print(f"\n{'='*60}")
        print(f"Processing Summary:")
        print(f"  Total files found: {len(html_files)}")
        print(f"  Successfully processed: {processed_count}")
        print(f"  Skipped (high density): {len(self.skipped_files)}")
        print(f"{'='*60}")
        
        self.df = pd.DataFrame(self.data)
        return self.df
    
    def save_to_csv(self, output_file='extracted_coordinates.csv'):
        """Save extracted data to CSV"""
        if hasattr(self, 'df') and len(self.df) > 0:
            output_path = os.path.join(self.directory_path, output_file)
            self.df.to_csv(output_path, index=False)
            print(f"\nData saved to: {output_path}")
            print(f"Total records: {len(self.df)}")
        else:
            print("No data to save. Run process_multiple_files() first.")
        
        # Save skipped files info
        if len(self.skipped_files) > 0:
            skipped_df = pd.DataFrame(self.skipped_files)
            skipped_path = os.path.join(self.directory_path, 'skipped_files.csv')
            skipped_df.to_csv(skipped_path, index=False)
            print(f"Skipped files info saved to: {skipped_path}")
    
    def print_summary(self):
        """Print summary statistics"""
        if not hasattr(self, 'df') or len(self.df) == 0:
            print("No data available. Run process_multiple_files() first.")
            return
        
        print("\n" + "="*60)
        print("EXTRACTION SUMMARY")
        print("="*60)
        print(f"Total files processed: {len(self.df)}")
        print(f"Total files skipped: {len(self.skipped_files)}")
        print(f"Files with Max Heat: {self.df['max_heat_lat'].notna().sum()}")
        print(f"Files with AVG: {self.df['avg_lat'].notna().sum()}")
        print(f"Files with Target: {self.df['target_lat'].notna().sum()}")
        print(f"Files with RX1: {self.df['rx1_lat'].notna().sum()}")
        
        if len(self.skipped_files) > 0:
            print(f"\nSkipped Files:")
            for skip_info in self.skipped_files[:5]:  # Show first 5
                print(f"  - {skip_info['filename']}: {skip_info['reason']}")
            if len(self.skipped_files) > 5:
                print(f"  ... and {len(self.skipped_files) - 5} more")
        
        if self.df['max_heat_lat'].notna().any():
            print(f"\nMax Heat Statistics:")
            print(f"  Latitude range: {self.df['max_heat_lat'].min():.6f} to {self.df['max_heat_lat'].max():.6f}")
            print(f"  Longitude range: {self.df['max_heat_long'].min():.6f} to {self.df['max_heat_long'].max():.6f}")
            if self.df['max_heat_value'].notna().any():
                print(f"  Value range: {self.df['max_heat_value'].min():.2f} to {self.df['max_heat_value'].max():.2f}")
        
        if self.df['avg_lat'].notna().any():
            print(f"\nAVG Statistics:")
            print(f"  Latitude range: {self.df['avg_lat'].min():.6f} to {self.df['avg_lat'].max():.6f}")
            print(f"  Longitude range: {self.df['avg_long'].min():.6f} to {self.df['avg_long'].max():.6f}")
            if self.df['avg_value'].notna().any():
                print(f"  Value range: {self.df['avg_value'].min():.2f} to {self.df['avg_value'].max():.2f}")
    
    def analyze_coordinate_distribution(self):
        """Analyze distribution of Max Heat and AVG coordinates"""
        if not hasattr(self, 'df') or len(self.df) == 0:
            print("No data available.")
            return None
        
        analysis = {
            'max_heat': {},
            'avg': {},
            'combined': {}
        }
        
        # Max Heat analysis
        max_heat_coords = self.df[['max_heat_lat', 'max_heat_long']].dropna()
        if len(max_heat_coords) > 0:
            analysis['max_heat'] = self._analyze_coords(
                max_heat_coords.values, 
                'Max Heat'
            )
        
        # AVG analysis
        avg_coords = self.df[['avg_lat', 'avg_long']].dropna()
        if len(avg_coords) > 0:
            analysis['avg'] = self._analyze_coords(
                avg_coords.values,
                'AVG'
            )
        
        # Combined analysis
        all_coords = pd.concat([
            max_heat_coords.rename(columns={'max_heat_lat': 'lat', 'max_heat_long': 'long'}),
            avg_coords.rename(columns={'avg_lat': 'lat', 'avg_long': 'long'})
        ])
        if len(all_coords) > 0:
            analysis['combined'] = self._analyze_coords(
                all_coords.values,
                'Combined'
            )
        
        return analysis
    
    def _analyze_coords(self, coords, label):
        """Perform statistical analysis on coordinates"""
        result = {
            'label': label,
            'count': len(coords),
            'mean': np.mean(coords, axis=0),
            'median': np.median(coords, axis=0),
            'std': np.std(coords, axis=0),
            'centroid': np.mean(coords, axis=0)
        }
        
        # Calculate distance from centroid for each point
        distances = [distance.euclidean(coord, result['centroid']) for coord in coords]
        result['max_distance_from_centroid'] = max(distances)
        result['avg_distance_from_centroid'] = np.mean(distances)
        
        return result
    
    def find_best_estimate_statistical(self, method='median', confidence_radius=0.001):
        """
        Find best estimate using statistical methods
        
        Methods:
        - 'mean': Average of all points
        - 'median': Median of all points (robust to outliers)
        - 'mode': Most frequent coordinate cluster
        - 'weighted_mean': Weighted by density values
        - 'trimmed_mean': Remove outliers then average
        """
        if not hasattr(self, 'df') or len(self.df) == 0:
            return None
        
        results = {}
        
        # Method 1: MEDIAN (Robust to outliers)
        if method in ['median', 'all']:
            max_heat_coords = self.df[['max_heat_lat', 'max_heat_long']].dropna().values
            avg_coords = self.df[['avg_lat', 'avg_long']].dropna().values
            
            if len(max_heat_coords) > 0:
                results['max_heat_median'] = {
                    'lat': np.median(max_heat_coords[:, 0]),
                    'long': np.median(max_heat_coords[:, 1]),
                    'method': 'Median',
                    'confidence': self._calculate_confidence(max_heat_coords, np.median(max_heat_coords, axis=0))
                }
            
            if len(avg_coords) > 0:
                results['avg_median'] = {
                    'lat': np.median(avg_coords[:, 0]),
                    'long': np.median(avg_coords[:, 1]),
                    'method': 'Median',
                    'confidence': self._calculate_confidence(avg_coords, np.median(avg_coords, axis=0))
                }
        
        # Method 2: WEIGHTED MEAN (by density value)
        if method in ['weighted_mean', 'all']:
            max_heat_data = self.df[['max_heat_lat', 'max_heat_long', 'max_heat_value']].dropna()
            if len(max_heat_data) > 0:
                weights = max_heat_data['max_heat_value'].values
                weighted_lat = np.average(max_heat_data['max_heat_lat'], weights=weights)
                weighted_long = np.average(max_heat_data['max_heat_long'], weights=weights)
                
                results['max_heat_weighted'] = {
                    'lat': weighted_lat,
                    'long': weighted_long,
                    'method': 'Weighted Mean',
                    'confidence': self._calculate_confidence(
                        max_heat_data[['max_heat_lat', 'max_heat_long']].values,
                        np.array([weighted_lat, weighted_long])
                    )
                }
        
        # Method 3: TRIMMED MEAN (remove outliers)
        if method in ['trimmed_mean', 'all']:
            max_heat_coords = self.df[['max_heat_lat', 'max_heat_long']].dropna().values
            if len(max_heat_coords) > 5:
                trimmed_coords = self._remove_outliers(max_heat_coords, percentile=10)
                results['max_heat_trimmed'] = {
                    'lat': np.mean(trimmed_coords[:, 0]),
                    'long': np.mean(trimmed_coords[:, 1]),
                    'method': 'Trimmed Mean (90%)',
                    'confidence': self._calculate_confidence(trimmed_coords, np.mean(trimmed_coords, axis=0)),
                    'points_used': len(trimmed_coords),
                    'points_removed': len(max_heat_coords) - len(trimmed_coords)
                }
        
        return results
    
    def find_best_estimate_clustering(self, method='dbscan', eps=0.001, min_samples=3):
        """
        Find best estimate using clustering methods
        
        Methods:
        - 'dbscan': Density-based clustering
        - 'kmeans': K-means clustering
        - 'hierarchical': Hierarchical clustering
        """
        if not hasattr(self, 'df') or len(self.df) == 0:
            return None
        
        results = {}
        
        # Get coordinates
        max_heat_coords = self.df[['max_heat_lat', 'max_heat_long']].dropna().values
        avg_coords = self.df[['avg_lat', 'avg_long']].dropna().values
        all_coords = np.vstack([max_heat_coords, avg_coords]) if len(avg_coords) > 0 else max_heat_coords
        
        if len(all_coords) < min_samples:
            print(f"Not enough points for clustering (need at least {min_samples})")
            return None
        
        # Method 1: DBSCAN (finds dense regions)
        if method in ['dbscan', 'all']:
            db = DBSCAN(eps=eps, min_samples=min_samples).fit(all_coords)
            labels = db.labels_
            
            # Find largest cluster
            unique_labels, counts = np.unique(labels[labels != -1], return_counts=True)
            if len(unique_labels) > 0:
                largest_cluster_label = unique_labels[np.argmax(counts)]
                cluster_points = all_coords[labels == largest_cluster_label]
                
                results['dbscan_largest_cluster'] = {
                    'lat': np.mean(cluster_points[:, 0]),
                    'long': np.mean(cluster_points[:, 1]),
                    'method': 'DBSCAN - Largest Cluster',
                    'cluster_size': len(cluster_points),
                    'total_clusters': len(unique_labels),
                    'outliers': np.sum(labels == -1),
                    'confidence': self._calculate_confidence(cluster_points, np.mean(cluster_points, axis=0))
                }
        
        # Method 2: K-Means with optimal K
        if method in ['kmeans', 'all']:
            optimal_k = self._find_optimal_k(all_coords, max_k=min(10, len(all_coords)//2))
            if optimal_k > 0:
                kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init=10).fit(all_coords)
                
                # Find cluster with most points
                cluster_sizes = np.bincount(kmeans.labels_)
                largest_cluster_idx = np.argmax(cluster_sizes)
                cluster_center = kmeans.cluster_centers_[largest_cluster_idx]
                
                results['kmeans_largest_cluster'] = {
                    'lat': cluster_center[0],
                    'long': cluster_center[1],
                    'method': f'K-Means (k={optimal_k})',
                    'cluster_size': cluster_sizes[largest_cluster_idx],
                    'total_clusters': optimal_k,
                    'confidence': self._calculate_confidence(
                        all_coords[kmeans.labels_ == largest_cluster_idx],
                        cluster_center
                    )
                }
        
        return results
    
    def find_best_estimate_consensus(self, threshold_distance=0.001, min_consensus=0.5):
        """
        Find best estimate using consensus voting
        Points that are close to each other "vote" for a location
        """
        if not hasattr(self, 'df') or len(self.df) == 0:
            return None
        
        max_heat_coords = self.df[['max_heat_lat', 'max_heat_long']].dropna().values
        
        if len(max_heat_coords) < 3:
            return None
        
        # Calculate pairwise distances
        dist_matrix = distance.cdist(max_heat_coords, max_heat_coords)
        
        # Count neighbors within threshold for each point
        neighbor_counts = np.sum(dist_matrix < threshold_distance, axis=1)
        
        # Find point with most neighbors
        best_idx = np.argmax(neighbor_counts)
        consensus_point = max_heat_coords[best_idx]
        consensus_count = neighbor_counts[best_idx]
        
        # Get all points in consensus region
        consensus_region = max_heat_coords[dist_matrix[best_idx] < threshold_distance]
        
        result = {
            'lat': np.mean(consensus_region[:, 0]),
            'long': np.mean(consensus_region[:, 1]),
            'method': 'Consensus Voting',
            'consensus_points': len(consensus_region),
            'consensus_ratio': len(consensus_region) / len(max_heat_coords),
            'confidence': self._calculate_confidence(consensus_region, np.mean(consensus_region, axis=0))
        }
        
        return result
    
    def find_best_estimate_combined(self):
        """
        Combine multiple methods and return best estimate with confidence scores
        """
        print("\n" + "="*70)
        print("COMBINED ESTIMATION ANALYSIS")
        print("="*70)
        
        estimates = []
        
        # Statistical methods
        stat_results = self.find_best_estimate_statistical(method='all')
        if stat_results:
            for key, val in stat_results.items():
                estimates.append({**val, 'source': key})
        
        # Clustering methods
        cluster_results = self.find_best_estimate_clustering(method='all')
        if cluster_results:
            for key, val in cluster_results.items():
                estimates.append({**val, 'source': key})
        
        # Consensus method
        consensus_result = self.find_best_estimate_consensus()
        if consensus_result:
            estimates.append({**consensus_result, 'source': 'consensus'})
        
        if not estimates:
            print("No estimates could be generated.")
            return None
        
        # Rank estimates by confidence
        estimates_sorted = sorted(estimates, key=lambda x: x.get('confidence', 0), reverse=True)
        
        # Print all estimates
        print(f"\nTotal estimates generated: {len(estimates_sorted)}\n")
        
        for i, est in enumerate(estimates_sorted, 1):
            print(f"{i}. {est['method']} ({est['source']})")
            print(f"   Coordinates: ({est['lat']:.6f}, {est['long']:.6f})")
            print(f"   Confidence: {est.get('confidence', 0):.1f}%")
            if 'cluster_size' in est:
                print(f"   Cluster Size: {est['cluster_size']}")
            if 'consensus_ratio' in est:
                print(f"   Consensus Ratio: {est['consensus_ratio']:.1%}")
            print()
        
        # Calculate final recommendation (average of top 3 estimates)
        top_n = min(3, len(estimates_sorted))
        final_lat = np.mean([est['lat'] for est in estimates_sorted[:top_n]])
        final_long = np.mean([est['long'] for est in estimates_sorted[:top_n]])
        final_confidence = np.mean([est.get('confidence', 0) for est in estimates_sorted[:top_n]])
        
        print("="*70)
        print("FINAL RECOMMENDATION (Average of Top 3 Methods)")
        print("="*70)
        print(f"Estimated Target: ({final_lat:.6f}, {final_long:.6f})")
        print(f"Confidence Score: {final_confidence:.1f}%")
        print(f"Based on: {', '.join([e['method'] for e in estimates_sorted[:top_n]])}")
        print("="*70)
        
        return {
            'all_estimates': estimates_sorted,
            'final_estimate': {
                'lat': final_lat,
                'long': final_long,
                'confidence': final_confidence,
                'method': 'Combined Top-3 Average'
            }
        }
    
    def _calculate_confidence(self, coords, estimate_point):
        """
        Enhanced confidence calculation with multiple factors
        """
        if len(coords) == 0:
            return 0.0
        
        distances = [distance.euclidean(coord, estimate_point) for coord in coords]
        avg_distance = np.mean(distances)
        std_distance = np.std(distances)
        
        # Factor 1: Distance-based confidence (closer points = higher confidence)
        # Scale adjusted for TDOA coordinates (degrees)
        distance_confidence = 100 / (1 + avg_distance * 1000 + std_distance * 1000)
        
        # Factor 2: Consistency factor (lower std = more consistent)
        if avg_distance > 0:
            consistency_factor = 1 - min(std_distance / avg_distance, 1.0)
        else:
            consistency_factor = 1.0
        
        # Factor 3: Sample size factor (more points = higher confidence)
        sample_confidence = min(len(coords) / 20, 1.0)  # Max at 20+ points
        
        # Combined confidence with weights
        final_confidence = (
            distance_confidence * 0.5 +  # 50% weight on distance
            consistency_factor * 100 * 0.3 +  # 30% weight on consistency
            sample_confidence * 100 * 0.2  # 20% weight on sample size
        )
        
        return min(100, final_confidence)
    
    def improve_estimates_with_filtering(self, 
                                        min_density_threshold=0.3,
                                        time_window_filter=True,
                                        outlier_removal_method='iqr'):
        """
        Improve confidence by filtering data before estimation
        
        Args:
            min_density_threshold: Minimum density value to consider (0-1)
            time_window_filter: Use sliding time window for temporal consistency
            outlier_removal_method: 'iqr', 'zscore', or 'isolation_forest'
        """
        if not hasattr(self, 'df') or len(self.df) == 0:
            return None
        
        print("\n" + "="*70)
        print("DATA FILTERING FOR IMPROVED CONFIDENCE")
        print("="*70)
        
        original_count = len(self.df)
        filtered_df = self.df.copy()
        
        # Filter 1: Remove low-density estimates
        if 'max_heat_value' in filtered_df.columns:
            before = len(filtered_df)
            filtered_df = filtered_df[
                (filtered_df['max_heat_value'].isna()) | 
                (filtered_df['max_heat_value'] >= min_density_threshold)
            ]
            removed = before - len(filtered_df)
            print(f"Filter 1 (Low Density): Removed {removed} points")
        
        # Filter 2: Temporal consistency (consecutive measurements should be close)
        if time_window_filter and len(filtered_df) > 3:
            coords = filtered_df[['max_heat_lat', 'max_heat_long']].dropna().values
            if len(coords) > 3:
                # Calculate moving average
                window_size = 3
                moving_avg = np.array([
                    np.mean(coords[max(0, i-window_size):i+window_size+1], axis=0)
                    for i in range(len(coords))
                ])
                
                # Keep points within 2 std of moving average
                distances_from_ma = [
                    distance.euclidean(coords[i], moving_avg[i])
                    for i in range(len(coords))
                ]
                threshold = np.mean(distances_from_ma) + 2 * np.std(distances_from_ma)
                
                valid_indices = filtered_df[filtered_df['max_heat_lat'].notna()].index
                keep_mask = np.array(distances_from_ma) <= threshold
                keep_indices = valid_indices[keep_mask]
                
                before = len(filtered_df)
                filtered_df = filtered_df.loc[
                    filtered_df.index.isin(keep_indices) | 
                    filtered_df['max_heat_lat'].isna()
                ]
                removed = before - len(filtered_df)
                print(f"Filter 2 (Temporal Consistency): Removed {removed} points")
        
        # Filter 3: Remove statistical outliers
        if outlier_removal_method and len(filtered_df) > 5:
            coords = filtered_df[['max_heat_lat', 'max_heat_long']].dropna().values
            
            if outlier_removal_method == 'iqr':
                # IQR method (most robust)
                centroid = np.mean(coords, axis=0)
                distances = [distance.euclidean(coord, centroid) for coord in coords]
                
                Q1 = np.percentile(distances, 25)
                Q3 = np.percentile(distances, 75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                valid_mask = (np.array(distances) >= lower_bound) & (np.array(distances) <= upper_bound)
                
            elif outlier_removal_method == 'zscore':
                # Z-score method
                from scipy import stats
                centroid = np.mean(coords, axis=0)
                distances = [distance.euclidean(coord, centroid) for coord in coords]
                z_scores = np.abs(stats.zscore(distances))
                valid_mask = z_scores < 3
            
            else:  # isolation_forest
                from sklearn.ensemble import IsolationForest
                iso_forest = IsolationForest(contamination=0.1, random_state=42)
                outliers = iso_forest.fit_predict(coords)
                valid_mask = outliers == 1
            
            valid_indices = filtered_df[filtered_df['max_heat_lat'].notna()].index
            keep_indices = valid_indices[valid_mask]
            
            before = len(filtered_df)
            filtered_df = filtered_df.loc[
                filtered_df.index.isin(keep_indices) | 
                filtered_df['max_heat_lat'].isna()
            ]
            removed = before - len(filtered_df)
            print(f"Filter 3 (Outlier Removal - {outlier_removal_method}): Removed {removed} points")
        
        print(f"\nTotal: {original_count} → {len(filtered_df)} points")
        print(f"Removed: {original_count - len(filtered_df)} ({(original_count - len(filtered_df))/original_count*100:.1f}%)")
        print("="*70)
        
        # Store filtered data
        self.filtered_df = filtered_df
        
        return filtered_df
    
    def find_best_estimate_combined(self, use_filtered=False):
        """
        Combine multiple methods and return best estimate with confidence scores
        
        Args:
            use_filtered: Use filtered data for higher confidence
        """
        print("\n" + "="*70)
        print("COMBINED ESTIMATION ANALYSIS")
        print("="*70)
        
        # Choose dataset
        if use_filtered and hasattr(self, 'filtered_df'):
            df = self.filtered_df
            print(f"Using FILTERED dataset ({len(df)} points)")
        else:
            df = self.df
            print(f"Using ORIGINAL dataset ({len(df)} points)")
        
        # Temporarily swap df for estimation
        original_df = self.df
        self.df = df
        
        estimates = []
        
        # Statistical methods
        stat_results = self.find_best_estimate_statistical(method='all')
        if stat_results:
            for key, val in stat_results.items():
                estimates.append({**val, 'source': key})
        
        # Clustering methods with adaptive parameters
        max_heat_coords = df[['max_heat_lat', 'max_heat_long']].dropna().values
        
        # Adaptive eps for DBSCAN based on data spread
        if len(max_heat_coords) > 3:
            from scipy.spatial.distance import pdist
            distances = pdist(max_heat_coords)
            adaptive_eps = np.percentile(distances, 10)  # 10th percentile
            cluster_results = self.find_best_estimate_clustering(
                method='all', 
                eps=adaptive_eps, 
                min_samples=max(3, len(max_heat_coords) // 10)
            )
            if cluster_results:
                for key, val in cluster_results.items():
                    estimates.append({**val, 'source': key})
        
        # Consensus method with adaptive threshold
        if len(max_heat_coords) > 3:
            adaptive_threshold = np.std([
                distance.euclidean(coord, np.mean(max_heat_coords, axis=0))
                for coord in max_heat_coords
            ]) / 2
            consensus_result = self.find_best_estimate_consensus(
                threshold_distance=adaptive_threshold
            )
            if consensus_result:
                estimates.append({**consensus_result, 'source': 'consensus'})
        
        # Restore original df
        self.df = original_df
        
        if not estimates:
            print("No estimates could be generated.")
            return None
        
        # Rank estimates by confidence
        estimates_sorted = sorted(estimates, key=lambda x: x.get('confidence', 0), reverse=True)
        
        # Print all estimates
        print(f"\nTotal estimates generated: {len(estimates_sorted)}\n")
        
        for i, est in enumerate(estimates_sorted, 1):
            print(f"{i}. {est['method']} ({est['source']})")
            print(f"   Coordinates: ({est['lat']:.6f}, {est['long']:.6f})")
            print(f"   Confidence: {est.get('confidence', 0):.1f}%")
            if 'cluster_size' in est:
                print(f"   Cluster Size: {est['cluster_size']}")
            if 'consensus_ratio' in est:
                print(f"   Consensus Ratio: {est['consensus_ratio']:.1%}")
            if 'points_used' in est:
                print(f"   Points Used: {est['points_used']}")
            print()
        
        # Weighted average (higher confidence = more weight)
        top_n = min(5, len(estimates_sorted))
        weights = np.array([est.get('confidence', 0) for est in estimates_sorted[:top_n]])
        weights = weights / weights.sum()  # Normalize
        
        final_lat = np.average([est['lat'] for est in estimates_sorted[:top_n]], weights=weights)
        final_long = np.average([est['long'] for est in estimates_sorted[:top_n]], weights=weights)
        final_confidence = np.average([est.get('confidence', 0) for est in estimates_sorted[:top_n]], weights=weights)
        
        print("="*70)
        print("FINAL RECOMMENDATION (Weighted Average of Top 5 Methods)")
        print("="*70)
        print(f"Estimated Target: ({final_lat:.6f}, {final_long:.6f})")
        print(f"Confidence Score: {final_confidence:.1f}%")
        print(f"Based on: {', '.join([e['method'] for e in estimates_sorted[:top_n]])}")
        
        # Calculate uncertainty radius (in meters)
        coords_for_uncertainty = df[['max_heat_lat', 'max_heat_long']].dropna().values
        if len(coords_for_uncertainty) > 0:
            distances_from_final = [
                distance.euclidean(coord, [final_lat, final_long])
                for coord in coords_for_uncertainty
            ]
            uncertainty_radius_deg = np.std(distances_from_final)
            uncertainty_radius_m = uncertainty_radius_deg * 111000  # Approximate conversion
            print(f"Uncertainty Radius: ±{uncertainty_radius_m:.1f} meters")
        
        print("="*70)
        
        return {
            'all_estimates': estimates_sorted,
            'final_estimate': {
                'lat': final_lat,
                'long': final_long,
                'confidence': final_confidence,
                'method': 'Weighted Average Top-5',
                'uncertainty_m': uncertainty_radius_m if len(coords_for_uncertainty) > 0 else None
            }
        }

    def create_combined_map(self, output_file='combined_tdoa_map.html', enable_clustering=True, estimation_results=None):
        """Create combined HTML map with all markers, optional clustering, and estimation results"""
        if not hasattr(self, 'df') or len(self.df) == 0:
            print("No data available. Run process_multiple_files() first.")
            return
        
        # Calculate center point
        all_lats = pd.concat([self.df['max_heat_lat'], self.df['avg_lat']]).dropna()
        all_longs = pd.concat([self.df['max_heat_long'], self.df['avg_long']]).dropna()
        
        if len(all_lats) == 0 or len(all_longs) == 0:
            print("No valid coordinates found in any file.")
            return
        
        center_lat = all_lats.mean()
        center_long = all_longs.mean()
        
        # Get reference points from first valid entry
        rx1_lat = self.df['rx1_lat'].dropna().iloc[0] if self.df['rx1_lat'].notna().any() else -7.2774382
        rx1_long = self.df['rx1_long'].dropna().iloc[0] if self.df['rx1_long'].notna().any() else 112.79304
        rx2_lat = self.df['rx2_lat'].dropna().iloc[0] if self.df['rx2_lat'].notna().any() else -7.3208236
        rx2_long = self.df['rx2_long'].dropna().iloc[0] if self.df['rx2_long'].notna().any() else 112.70028
        rx3_lat = self.df['rx3_lat'].dropna().iloc[0] if self.df['rx3_lat'].notna().any() else -7.357257
        rx3_long = self.df['rx3_long'].dropna().iloc[0] if self.df['rx3_long'].notna().any() else 112.67702
        
        target_lat = self.df['target_lat'].dropna().iloc[0] if self.df['target_lat'].notna().any() else -7.3200864
        target_long = self.df['target_long'].dropna().iloc[0] if self.df['target_long'].notna().any() else 112.73128
        ref_lat = self.df['reference_lat'].dropna().iloc[0] if self.df['reference_lat'].notna().any() else -7.3250054
        ref_long = self.df['reference_long'].dropna().iloc[0] if self.df['reference_long'].notna().any() else 112.73803
        
        # Clustering CSS and JS with HTTPS
        cluster_css = ""
        cluster_js = ""
        if enable_clustering:
            cluster_css = """
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css" />"""
            cluster_js = """
  <script src="https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js"></script>"""
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
<title>Combined TDOA Results Map with Estimations</title>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" 
      integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>{cluster_css}
<style>
  #map {{ width: 100%; height: 900px; }}
  .info {{
    padding: 6px 8px;
    font: 14px/16px Arial, Helvetica, sans-serif;
    background: white;
    background: rgba(255,255,255,0.9);
    box-shadow: 0 0 15px rgba(0,0,0,0.2);
    border-radius: 5px;
    max-height: 400px;
    overflow-y: auto;
  }}
  .info h4 {{
    margin: 0 0 5px;
    color: #777;
  }}
  .legend {{
    line-height: 18px;
    color: #555;
  }}
  .legend i {{
    width: 18px;
    height: 18px;
    float: left;
    margin-right: 8px;
    opacity: 0.7;
  }}
  /* Custom cluster styling */
  .marker-cluster-small {{
    background-color: rgba(195, 11, 130, 0.6);
  }}
  .marker-cluster-small div {{
    background-color: rgba(195, 11, 130, 0.8);
  }}
  .marker-cluster-medium {{
    background-color: rgba(65, 105, 225, 0.6);
  }}
  .marker-cluster-medium div {{
    background-color: rgba(65, 105, 225, 0.8);
  }}
  .marker-cluster-large {{
    background-color: rgba(255, 69, 0, 0.6);
  }}
  .marker-cluster-large div {{
    background-color: rgba(255, 69, 0, 0.8);
  }}
</style>
</head>
<body>

<div id="map"></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" 
        integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>{cluster_js}

<script>
  var map = L.map("map").setView([{center_lat}, {center_long}], 13); 
  
  // Use HTTPS for tiles to avoid mixed content error
  L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
    attribution: "Map data &copy; <a href='https://openstreetmap.org'>OpenStreetMap</a>",
    maxZoom: 18,
  }}).addTo(map);
  
  L.control.scale().addTo(map);

  // Define custom icons
  var maxHeatIcon = L.divIcon({{
    className: 'custom-div-icon',
    html: "<div style='background-color:#c30b82;width:12px;height:12px;border-radius:50%;border:2px solid white;box-shadow:0 0 4px rgba(0,0,0,0.5);'></div>",
    iconSize: [12, 12],
    iconAnchor: [6, 6]
  }});

  var avgIcon = L.divIcon({{
    className: 'custom-div-icon',
    html: "<div style='background-color:#4169E1;width:12px;height:12px;border-radius:50%;border:2px solid white;box-shadow:0 0 4px rgba(0,0,0,0.5);'></div>",
    iconSize: [12, 12],
    iconAnchor: [6, 6]
  }});

  var receiverIcon = L.divIcon({{
    className: 'custom-div-icon',
    html: "<div style='background-color:#228B22;width:16px;height:16px;border-radius:50%;border:3px solid white;box-shadow:0 0 6px rgba(0,0,0,0.6);'></div>",
    iconSize: [16, 16],
    iconAnchor: [8, 8]
  }});

  var targetIcon = L.divIcon({{
    className: 'custom-div-icon',
    html: "<div style='background-color:#FF4500;width:18px;height:18px;transform:rotate(45deg);border:3px solid white;box-shadow:0 0 6px rgba(0,0,0,0.6);'></div>",
    iconSize: [18, 18],
    iconAnchor: [9, 9]
  }});

  // Estimation icons
  var estimateIcon = L.divIcon({{
    className: 'custom-div-icon',
    html: "<div style='background-color:#FFD700;width:20px;height:20px;border-radius:50%;border:4px solid #FF8C00;box-shadow:0 0 10px rgba(255,215,0,0.8);'></div>",
    iconSize: [20, 20],
    iconAnchor: [10, 10]
  }});

  var finalEstimateIcon = L.divIcon({{
    className: 'custom-div-icon',
    html: "<div style='background-color:#00FF00;width:24px;height:24px;border-radius:50%;border:5px solid #00AA00;box-shadow:0 0 15px rgba(0,255,0,0.9);'><div style='background-color:#FFFFFF;width:8px;height:8px;border-radius:50%;position:absolute;top:8px;left:8px;'></div></div>",
    iconSize: [24, 24],
    iconAnchor: [12, 12]
  }});

  var estimateCircleIcon = L.divIcon({{
    className: 'custom-div-icon',
    html: "<div style='background-color:transparent;width:16px;height:16px;border:3px solid #FFD700;border-radius:50%;box-shadow:0 0 8px rgba(255,215,0,0.6);'></div>",
    iconSize: [16, 16],
    iconAnchor: [8, 8]
  }});

  // Add receiver positions (not clustered)
  L.marker([{rx1_lat}, {rx1_long}], {{
    icon: receiverIcon,
    title: 'Receiver 1'
  }}).addTo(map).bindPopup('<b>Receiver 1</b><br>Lat: {rx1_lat}<br>Long: {rx1_long}');

  L.marker([{rx2_lat}, {rx2_long}], {{
    icon: receiverIcon,
    title: 'Receiver 2'
  }}).addTo(map).bindPopup('<b>Receiver 2</b><br>Lat: {rx2_lat}<br>Long: {rx2_long}');

  L.marker([{rx3_lat}, {rx3_long}], {{
    icon: receiverIcon,
    title: 'Receiver 3'
  }}).addTo(map).bindPopup('<b>Receiver 3</b><br>Lat: {rx3_lat}<br>Long: {rx3_long}');

  // Add target position (not clustered)
  L.marker([{target_lat}, {target_long}], {{
    icon: targetIcon,
    title: 'Target'
  }}).addTo(map).bindPopup('<b>Target Position</b><br>Lat: {target_lat}<br>Long: {target_long}');

  // Add reference position (not clustered)
  L.marker([{ref_lat}, {ref_long}], {{
    icon: targetIcon,
    title: 'Reference'
  }}).addTo(map).bindPopup('<b>Reference Position</b><br>Lat: {ref_lat}<br>Long: {ref_long}');

"""
        
        if enable_clustering:
            html_content += """
  // Create marker cluster groups
  var maxHeatCluster = L.markerClusterGroup({
    maxClusterRadius: 50,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: true,
    zoomToBoundsOnClick: true,
    iconCreateFunction: function(cluster) {
      var childCount = cluster.getChildCount();
      var c = ' marker-cluster-';
      if (childCount < 10) {
        c += 'small';
      } else if (childCount < 50) {
        c += 'medium';
      } else {
        c += 'large';
      }
      return new L.DivIcon({ 
        html: '<div><span>' + childCount + '</span></div>', 
        className: 'marker-cluster' + c, 
        iconSize: new L.Point(40, 40) 
      });
    }
  });

  var avgCluster = L.markerClusterGroup({
    maxClusterRadius: 50,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: true,
    zoomToBoundsOnClick: true,
    iconCreateFunction: function(cluster) {
      var childCount = cluster.getChildCount();
      var c = ' marker-cluster-';
      if (childCount < 10) {
        c += 'small';
      } else if (childCount < 50) {
        c += 'medium';
      } else {
        c += 'large';
      }
      return new L.DivIcon({ 
        html: '<div><span>' + childCount + '</span></div>', 
        className: 'marker-cluster' + c, 
        iconSize: new L.Point(40, 40) 
      });
    }
  });

"""
        else:
            html_content += """
  // Layer groups for Max Heat and AVG (no clustering)
  var maxHeatCluster = L.layerGroup();
  var avgCluster = L.layerGroup();

"""
        
        # Add Max Heat markers
        for idx, row in self.df.iterrows():
            if pd.notna(row['max_heat_lat']) and pd.notna(row['max_heat_long']):
                value_str = f"{row['max_heat_value']:.1f}" if pd.notna(row['max_heat_value']) else "N/A"
                filename_safe = row['filename'].replace("'", "\\'")
                html_content += f"""
  L.marker([{row['max_heat_lat']}, {row['max_heat_long']}], {{
    icon: maxHeatIcon,
    title: 'Max Heat - {filename_safe}'
  }}).bindPopup('<b>Max Heat Point</b><br>File: {filename_safe}<br>Lat: {row['max_heat_lat']:.6f}<br>Long: {row['max_heat_long']:.6f}<br>Value: {value_str}').addTo(maxHeatCluster);
"""
        
        # Add AVG markers
        for idx, row in self.df.iterrows():
            if pd.notna(row['avg_lat']) and pd.notna(row['avg_long']):
                value_str = f"{row['avg_value']:.1f}" if pd.notna(row['avg_value']) else "N/A"
                filename_safe = row['filename'].replace("'", "\\'")
                html_content += f"""
  L.marker([{row['avg_lat']}, {row['avg_long']}], {{
    icon: avgIcon,
    title: 'AVG - {filename_safe}'
  }}).bindPopup('<b>AVG Point</b><br>File: {filename_safe}<br>Lat: {row['avg_lat']:.6f}<br>Long: {row['avg_long']:.6f}<br>Value: {value_str}').addTo(avgCluster);
"""
        
        # Add estimation markers if available
        estimation_layer_code = ""
        if estimation_results:
            html_content += """
  // Create estimation layer group
  var estimationLayer = L.layerGroup();

"""
            # Add all estimation points
            all_estimates = estimation_results.get('all_estimates', [])
            for i, estimate in enumerate(all_estimates[:10], 1):  # Show top 10
                lat = estimate['lat']
                long = estimate['long']
                method = estimate['method'].replace("'", "\\'")
                confidence = estimate.get('confidence', 0)
                source = estimate.get('source', '').replace("'", "\\'")
                
                popup_html = f"<b>Estimate #{i}: {method}</b><br>"
                popup_html += f"Lat: {lat:.6f}<br>"
                popup_html += f"Long: {long:.6f}<br>"
                popup_html += f"Confidence: {confidence:.1f}%<br>"
                popup_html += f"Source: {source}"
                
                if 'cluster_size' in estimate:
                    popup_html += f"<br>Cluster Size: {estimate['cluster_size']}"
                if 'consensus_ratio' in estimate:
                    popup_html += f"<br>Consensus: {estimate['consensus_ratio']:.1%}"
                
                html_content += f"""
  L.marker([{lat}, {long}], {{
    icon: estimateCircleIcon,
    title: 'Estimate: {method}'
  }}).bindPopup('{popup_html}').addTo(estimationLayer);
"""
            
            # Add final recommendation with special marker
            final_est = estimation_results.get('final_estimate', {})
            if final_est:
                final_lat = final_est['lat']
                final_long = final_est['long']
                final_conf = final_est.get('confidence', 0)
                final_method = final_est.get('method', 'Unknown').replace("'", "\\'")
                
                final_popup = f"<b>🎯 FINAL RECOMMENDATION</b><br>"
                final_popup += f"<b>Method:</b> {final_method}<br>"
                final_popup += f"<b>Latitude:</b> {final_lat:.6f}<br>"
                final_popup += f"<b>Longitude:</b> {final_long:.6f}<br>"
                final_popup += f"<b>Confidence:</b> {final_conf:.1f}%<br>"
                final_popup += f"<hr><small>This is the averaged result from top 3 estimation methods</small>"
                
                html_content += f"""
  // Add final recommendation marker
  L.marker([{final_lat}, {final_long}], {{
    icon: finalEstimateIcon,
    title: 'FINAL RECOMMENDATION',
    zIndexOffset: 1000
  }}).bindPopup('{final_popup}').addTo(map);

  // Add accuracy circle around final estimate
  L.circle([{final_lat}, {final_long}], {{
    color: '#00FF00',
    fillColor: '#00FF00',
    fillOpacity: 0.1,
    radius: 100,
    weight: 2
  }}).addTo(map).bindPopup('Estimated accuracy radius: 100m');

"""
            
            estimation_layer_code = """
  map.addLayer(estimationLayer);
  overlays["Estimation Points (Top 10)"] = estimationLayer;
"""
        
        # Add clusters to map and create layer control
        max_heat_count = self.df['max_heat_lat'].notna().sum()
        avg_count = self.df['avg_lat'].notna().sum()
        
        html_content += f"""
  // Add clusters to map
  map.addLayer(maxHeatCluster);
  map.addLayer(avgCluster);

  // Add layer control
  var overlays = {{
    "Max Heat Points ({max_heat_count})": maxHeatCluster,
    "AVG Points ({avg_count})": avgCluster
  }};
  {estimation_layer_code}
  L.control.layers(null, overlays, {{collapsed: false}}).addTo(map);

  // Add legend
  var legend = L.control({{position: 'bottomright'}});
  
  legend.onAdd = function (map) {{
    var div = L.DomUtil.create('div', 'info legend');
    div.innerHTML = '<h4>TDOA Results</h4>';
    div.innerHTML += '<i style="background:#c30b82;border-radius:50%;"></i> Max Heat Point (' + {max_heat_count} + ')<br>';
    div.innerHTML += '<i style="background:#4169E1;border-radius:50%;"></i> AVG Point (' + {avg_count} + ')<br>';
    div.innerHTML += '<i style="background:#228B22;border-radius:50%;"></i> Receivers (3)<br>';
    div.innerHTML += '<i style="background:#FF4500;transform:rotate(45deg);"></i> Target/Reference<br>';"""
        
        if estimation_results:
            html_content += """
    div.innerHTML += '<i style="background:#FFD700;border-radius:50%;border:2px solid #FF8C00;"></i> Estimation Points<br>';
    div.innerHTML += '<i style="background:#00FF00;border-radius:50%;border:2px solid #00AA00;"></i> Final Recommendation<br>';"""
        
        html_content += f"""
    div.innerHTML += '<hr><small>Total Files: {len(self.df)}</small><br>';
    div.innerHTML += '<small>Skipped Files: {len(self.skipped_files)}</small><br>';"""
        
        if enable_clustering:
            html_content += """
    div.innerHTML += '<small>Clustering: Enabled</small>';"""
        else:
            html_content += """
    div.innerHTML += '<small>Clustering: Disabled</small>';"""
        
        html_content += f"""
    return div;
  }};
  
  legend.addTo(map);

  // Add info box
  var info = L.control({{position: 'topleft'}});
  
  info.onAdd = function (map) {{
    var div = L.DomUtil.create('div', 'info');
    div.innerHTML = '<h4>Combined TDOA Map</h4>';
    div.innerHTML += '<b>Total Measurements:</b> {len(self.df)}<br>';
    div.innerHTML += '<b>Valid Max Heat:</b> {max_heat_count}<br>';
    div.innerHTML += '<b>Valid AVG:</b> {avg_count}<br>';
    div.innerHTML += '<b>Skipped (High Density):</b> {len(self.skipped_files)}<br>';"""
        
        if enable_clustering:
            html_content += """
    div.innerHTML += '<b>Clustering:</b> Enabled<br>';"""
        
        if estimation_results:
            final_est = estimation_results.get('final_estimate', {})
            if final_est:
                html_content += f"""
    div.innerHTML += '<hr><b>🎯 Final Estimate:</b><br>';
    div.innerHTML += '<small>Lat: {final_est['lat']:.6f}</small><br>';
    div.innerHTML += '<small>Long: {final_est['long']:.6f}</small><br>';
    div.innerHTML += '<small>Confidence: {final_est.get('confidence', 0):.1f}%</small>';"""
        
        html_content += """
    return div;
  };
  
  info.addTo(map);

</script>
</body>
</html>
"""
        
        # Write to file
        output_path = os.path.join(self.directory_path, output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"\n{'='*60}")
        print("MAP GENERATION COMPLETE")
        print(f"{'='*60}")
        print(f"Map saved to: {output_path}")
        print(f"Clustering: {'Enabled' if enable_clustering else 'Disabled'}")
        if estimation_results:
            print(f"Estimation markers: Added (Top 10 + Final)")
        print(f"Total Max Heat markers: {max_heat_count}")
        print(f"Total AVG markers: {avg_count}")
        print(f"Total files: {len(self.df)}")
        print(f"Skipped files: {len(self.skipped_files)}")

def main():
    """Main execution function"""
    
    # Configuration
    DIRECTORY = r"c:\Users\sd\Desktop\WIP\tdoa-radio-freq\TDOA-MATHLAB\data_121_hasil"
    PATTERN = "121map_933_1031_2025_6_12_9_*.html"
    START_MINUTE = 12
    END_MINUTE = 42
    ENABLE_CLUSTERING = True
    
    # NEW: Filtering options for higher confidence
    APPLY_FILTERING = True
    MIN_DENSITY = 0.3  # Minimum density threshold
    OUTLIER_METHOD = 'iqr'  # 'iqr', 'zscore', or 'isolation_forest'
    
    print("="*60)
    print("TDOA MAP EXTRACTOR AND COMBINER")
    print("="*60)
    print(f"Directory: {DIRECTORY}")
    print(f"Pattern: {PATTERN}")
    if START_MINUTE and END_MINUTE:
        print(f"Time Range: 09:{START_MINUTE:02d} - 09:{END_MINUTE:02d}")
    print(f"Skip Condition: Density > 0.9 with count > 50")
    print(f"Clustering: {'Enabled' if ENABLE_CLUSTERING else 'Disabled'}")
    print(f"Data Filtering: {'Enabled' if APPLY_FILTERING else 'Disabled'}")
    if APPLY_FILTERING:
        print(f"  Min Density: {MIN_DENSITY}")
        print(f"  Outlier Method: {OUTLIER_METHOD}")
    print("="*60)
    
    # Initialize extractor
    extractor = TDOAMapExtractor(directory_path=DIRECTORY)
    
    # Process files
    df = extractor.process_multiple_files(
        pattern=PATTERN,
        start_minute=START_MINUTE,
        end_minute=END_MINUTE
    )
    
    if len(df) == 0:
        print("\nNo data extracted. Exiting.")
        return
    
    # Save to CSV
    extractor.save_to_csv('tdoa_extracted_coordinates.csv')
    
    # Print summary
    extractor.print_summary()
    
    # NEW: Apply filtering for improved confidence
    if APPLY_FILTERING:
        filtered_df = extractor.improve_estimates_with_filtering(
            min_density_threshold=MIN_DENSITY,
            time_window_filter=True,
            outlier_removal_method=OUTLIER_METHOD
        )
        
        # Save filtered data
        if filtered_df is not None and len(filtered_df) > 0:
            filtered_path = os.path.join(DIRECTORY, 'tdoa_filtered_coordinates.csv')
            filtered_df.to_csv(filtered_path, index=False)
            print(f"\nFiltered data saved to: {filtered_path}")
    
    # Find best estimate using multiple methods
    estimation_results = extractor.find_best_estimate_combined(use_filtered=APPLY_FILTERING)
    
    # Compare with unfiltered (for analysis)
    if APPLY_FILTERING:
        print("\n" + "="*70)
        print("COMPARISON: Filtered vs Unfiltered")
        print("="*70)
        unfiltered_results = extractor.find_best_estimate_combined(use_filtered=False)
        
        if estimation_results and unfiltered_results:
            print(f"Filtered Confidence: {estimation_results['final_estimate']['confidence']:.1f}%")
            print(f"Unfiltered Confidence: {unfiltered_results['final_estimate']['confidence']:.1f}%")
            print(f"Improvement: {estimation_results['final_estimate']['confidence'] - unfiltered_results['final_estimate']['confidence']:.1f}%")
    
    # Display sample data
    if len(df) > 0:
        print("\n" + "="*60)
        print("SAMPLE DATA (First 5 records)")
        print("="*60)
        cols_to_show = ['filename', 'max_heat_lat', 'max_heat_long', 'avg_lat', 'avg_long']
        available_cols = [col for col in cols_to_show if col in df.columns]
        print(df[available_cols].head())
    
    # Create combined map WITH ESTIMATION MARKERS
    extractor.create_combined_map(
        'combined_tdoa_results_with_estimates.html', 
        enable_clustering=ENABLE_CLUSTERING,
        estimation_results=estimation_results
    )
    
    print("\n" + "="*60)
    print("PROCESS COMPLETED SUCCESSFULLY")
    print("="*60)


if __name__ == "__main__":
    main()