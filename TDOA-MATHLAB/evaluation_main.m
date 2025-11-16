function evaluation_main(varargin)
% =========================================================================
%  Experimental Evaluation Script for RTL-SDR based TDOA
%  DC9ST, 2017-2019
% =========================================================================
%
% Usage:
%   evaluation_main()                          % uses default config
%   evaluation_main('filename.dat')           % uses specified file
%   evaluation_main('--file', 'filename.dat') % alternative syntax
%
% Examples:
%   evaluation_main('933_1031_2025_6_12_9_21.dat')
%   evaluation_main('--file', '933_1031_2025_6_12_9_21.dat')

% Parse input arguments
if nargin == 0
    % No arguments, use default config
    file_override = '';
elseif nargin == 1
    % Single argument - assume it's a filename
    file_override = varargin{1};
elseif nargin == 2 && strcmp(varargin{1}, '--file')
    % Two arguments with --file flag
    file_override = varargin{2};
else
    error('Invalid arguments. Usage: evaluation_main() or evaluation_main(''filename.dat'') or evaluation_main(''--file'', ''filename.dat'')');
end

disp(['file override: ' file_override]);

% adds subfolder with functions to PATH
[p,~,~] = fileparts(mfilename('fullpath'));
addpath([p '/functions']);
%addpath([p '/test']); % only required for the test setups
addpath([p '/coba']); % only required for the test setups


%% Config for TDOA setup

% RX and Ref TX Position
rx3_lat = -7.3572570; % RX 3 Bu Rini
rx3_long = 112.6770160;

rx2_lat = -7.2774382; % RX 2 Pak Tri Budi
rx2_long = 112.7930353;

rx1_lat = -7.22795569; % RX 1 Sontoh Laut -7.22795569, 112.68459984
rx1_long = 112.68459984;

tx_ref_lat = -7.2885674 ; % Referensi Radio SS titik gmaps 1000
tx_ref_long = 112.6993234;
% tx_ref_lat = -7.3200864; % Referensi Radio Gen FM titik gmaps 1031
% tx_ref_long = 112.7312756;
% tx_ref_lat = -7.2902441; % Referensi TVRI titik gmaps 5860
% tx_ref_long = 112.7139568;
% tx_ref_lat = -7.3250054; % Referensi 933
% tx_ref_long = 112.7380274;
% tx_ref_lat = -7.3200864; % Referensi 1031
% tx_ref_long = 112.7312756;

% tx_cari_lat = -7.3250054; % cari el-victor 933
% tx_cari_long = 112.7380274;
% tx_cari_lat = -7.3200864; % cari Gen FM 1031
% tx_cari_long = 112.7312756;

tx_cari_lat = -7.2816454; % cari Radio Suara Muslim 938
tx_cari_long = 112.7461872;
% tx_cari_lat = -7.2755979; % cari Radio Sonora 980
% tx_cari_long = 112.6846293;
% tx_cari_lat = -7.2734006; % cari Radio EBS 1059
% tx_cari_long = 112.7490406;

center_point_lat = -7.27513819; % center point
center_point_long = 112.7263886; % center point

% signal processing parameters
%signal_bandwidth_khz = 0;  % 400, 200, 40, 12, 0(no)
signal_bandwidth_khz = 40;  % 400, 200, 40, 12, 0(no)
smoothing_factor = 0;
% smoothing_factor = 3;

%corr_type = 'dphase';  %'abs' or 'dphase'
corr_type = 'dphase';  %'abs' or 'dphase'
interpol_factor = 0;

% additional processing of ref signal
%(set to > 0 only when other signals than the ref signal falls into the full RX bandwidth)
ref_bandwidth_khz = 40; % 400, 200, 40, 12, 0(no)
smoothing_factor_ref = 0;
% smoothing_factor_ref = 3;

% 0: no plots
% 1: show correlation plots
% 2: show also input spcetrograms and spectra of input meas
% 3: show also before and after filtering
report_level = 0;

% map output
% 'open_street_map' (default) or 'google_maps'
map_mode = 'open_street_map';

% heatmap (only with google maps)
heatmap_resolution = 200; % resolution for heatmap points
heatmap_threshold = 0.70;  % heatmap point with lower mag are suppressed for html output
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% Override file_identifier if provided as argument
if ~isempty(file_override)
    disp(['Overriding config file_identifier with: ' file_override]);
    file_identifier = file_override;
else
    disp(['Using file from config: ' file_override]);
end

% base folder
folder_identifier = 'data-november/';
folder_result = 'data-nov-hasil/';

% create filenames
dateiname1 = [folder_identifier '1_' file_identifier];
dateiname2 = [folder_identifier '2_' file_identifier];
dateiname3 = [folder_identifier '3_' file_identifier];

% calculate geodetic reference point as mean center of all RX positions
geo_ref_lat  = mean([rx1_lat, rx2_lat, rx3_lat]);
geo_ref_long = mean([rx1_long, rx2_long, rx3_long]);
disp(['geodetic reference point (mean of RX positions): lat=' num2str(geo_ref_lat, 8) ', long=' num2str(geo_ref_long, 8) ])

% known signal path differences between two RXes to Ref (sign of result is important!)
rx_distance_diff12 = dist_latlong(tx_ref_lat, tx_ref_long, rx1_lat, rx1_long, geo_ref_lat, geo_ref_long) - dist_latlong(tx_ref_lat, tx_ref_long, rx2_lat, rx2_long, geo_ref_lat, geo_ref_long); % (Ref to RX1 - Ref to RX2) in meters
rx_distance_diff13 = dist_latlong(tx_ref_lat, tx_ref_long, rx1_lat, rx1_long, geo_ref_lat, geo_ref_long) - dist_latlong(tx_ref_lat, tx_ref_long, rx3_lat, rx3_long, geo_ref_lat, geo_ref_long); % (Ref to RX1 - Ref to RX3) in meters
rx_distance_diff23 = dist_latlong(tx_ref_lat, tx_ref_long, rx2_lat, rx2_long, geo_ref_lat, geo_ref_long) - dist_latlong(tx_ref_lat, tx_ref_long, rx3_lat, rx3_long, geo_ref_lat, geo_ref_long); % (Ref to RX2 - Ref to RX3) in meters

% distance between two RXes in meters
rx_distance12 = dist_latlong(rx1_lat, rx1_long, rx2_lat, rx2_long, geo_ref_lat, geo_ref_long);
rx_distance13 = dist_latlong(rx1_lat, rx1_long, rx3_lat, rx3_long, geo_ref_lat, geo_ref_long);
rx_distance23 = dist_latlong(rx2_lat, rx2_long, rx3_lat, rx3_long, geo_ref_lat, geo_ref_long);

%% Read Signals from File
disp('______________________________________________________________________________________________');
disp('READ DATA FROM FILES');
signal1 = read_file_iq(dateiname1);
signal2 = read_file_iq(dateiname2);
signal3 = read_file_iq(dateiname3);

if (report_level > 1)
    % display raw signals
    num_samples_total = length(signal1);
    inphase1 = real(signal1);
    quadrature1 = imag(signal1);
    inphase2 = real(signal2);
    quadrature2 = imag(signal2);
    inphase3 = real(signal3);
    quadrature3 = imag(signal3);
    
    figure;
    subplot(3,1,1);
    plot(1:num_samples_total, inphase1(1:num_samples_total), 1:num_samples_total, quadrature1(1:num_samples_total));
    title('raw RX 1: I and Q');
    subplot(3,1,2);
    plot(1:num_samples_total, inphase2(1:num_samples_total), 1:num_samples_total, quadrature2(1:num_samples_total));
    title('raw RX 2: I and Q');
    subplot(3,1,3);
    plot(1:num_samples_total, inphase3(1:num_samples_total), 1:num_samples_total, quadrature3(1:num_samples_total));
    title('raw RX 3: I and Q');
    % return;
end

% if (report_level > 1)
%     % calculate and show spectrogram
%     nfft = 256;
%     overlap = 8;

%     figure;
%     subplot(4,2,1);
%     complex_signal = detrend(signal1);
%     [S,F,T,P] = spectrogram(complex_signal, nfft, overlap, nfft, 2e6 );
%     spectrum = fftshift(fliplr(10*log10(abs(P))'), 2);
%     for i=1:nfft
%         spectrum(:,i) = smooth(spectrum(:,i),9);
%     end
%     surf(T,F, spectrum', 'edgecolor', 'none');
%     axis tight;
%     view(0,90);
%     title('RX 1');
%     xlabel('time');
%     ylabel('frequency');

%     subplot(4,2,3);
%     complex_signal = detrend(signal2);
%     [S,F,T,P] = spectrogram(complex_signal, nfft, overlap, nfft, 2e6 );
%     spectrum = fftshift(fliplr(10*log10(abs(P))'), 2);
%     for i=1:nfft
%         spectrum(:,i) = smooth(spectrum(:,i),9);
%     end
%     surf(T,F, spectrum', 'edgecolor', 'none');
%     axis tight;
%     view(0,90);
%     title('RX 2');
%     xlabel('time');
%     ylabel('frequency');


%     subplot(4,2,5);
%     complex_signal = detrend(signal3);
%     [S,F,T,P] = spectrogram(complex_signal, nfft, overlap, nfft, 2e6 );
%     spectrum = fftshift(fliplr(10*log10(abs(P))'), 2);
%     for i=1:nfft
%         spectrum(:,i) = smooth(spectrum(:,i),9);
%     end
%     surf(T,F, spectrum', 'edgecolor', 'none');
%     axis tight;
%     view(0,90);
%     title('RX 3');
%     xlabel('time');
%     ylabel('frequency');

%     % display spectrum
%     spectrum_smooth_factor  = 201;
%     subplot(4,2,2);
%     spectrum_single1 = 10*log10(abs(fftshift(fft(signal1(1.7e6 : 1.7e6 + 2^18)))));
%     spectrum_single1 = smooth(spectrum_single1, spectrum_smooth_factor);
%     plot(spectrum_single1);
%     title('Measurement RX 1');
%     grid;

%     subplot(4,2,4);
%     spectrum_single2 = 10*log10(abs(fftshift(fft(signal2(1.7e6 : 1.7e6 + 2^18)))));
%     spectrum_single2 = smooth(spectrum_single2, spectrum_smooth_factor);
%     plot(spectrum_single2);
%     title('Measurement RX 2');
%     grid;

%     subplot(4,2,6);
%     spectrum_single3 = 10*log10(abs(fftshift(fft(signal3(1.7e6 : 1.7e6 + 2^18)))));
%     spectrum_single3 = smooth(spectrum_single3, spectrum_smooth_factor);
%     plot(spectrum_single3);
%     title('Measurement RX 3');
%     grid;

%     subplot(4,2,7:8);
%     freq_axis = -(length(spectrum_single1)/2) : 1 : ((length(spectrum_single1)/2)-1);
%     plot(freq_axis, spectrum_single1, freq_axis, spectrum_single2, freq_axis, spectrum_single3);
%     title('Measurement Signal RX 1,2 & 3');
%     grid;
% end;



%% Calculate TDOA
disp(' ');
disp('______________________________________________________________________________________________');
disp('CORRELATION 1 & 2');
[doa_meters12, doa_samples12, reliability12 ] = tdoa2(signal1, signal2, rx_distance_diff12, rx_distance12, ...
    smoothing_factor, corr_type, report_level, signal_bandwidth_khz, ...
    ref_bandwidth_khz, smoothing_factor_ref, interpol_factor);

disp(' ');
disp('______________________________________________________________________________________________');
disp('CORRELATION 1 & 3');
[doa_meters13, doa_samples13, reliability13 ] = tdoa2(signal1, signal3, rx_distance_diff13, rx_distance13, ...
    smoothing_factor, corr_type, report_level, signal_bandwidth_khz, ...
    ref_bandwidth_khz, smoothing_factor_ref, interpol_factor);

disp(' ');
disp('______________________________________________________________________________________________');
disp('CORRELATION 2 & 3');
[doa_meters23, doa_samples23, reliability23 ] = tdoa2(signal2, signal3, rx_distance_diff23, rx_distance23, ...
    smoothing_factor, corr_type, report_level, signal_bandwidth_khz, ...
    ref_bandwidth_khz, smoothing_factor_ref, interpol_factor);


%% Generate html map
disp(' ');
disp('______________________________________________________________________________________________');
disp('GENERATE HYPERBOLAS');

[points_lat1, points_long1] = gen_hyperbola(doa_meters12, rx1_lat, rx1_long, rx2_lat, rx2_long, geo_ref_lat, geo_ref_long, 'RX1', 'RX2');
[points_lat2, points_long2] = gen_hyperbola(doa_meters13, rx1_lat, rx1_long, rx3_lat, rx3_long, geo_ref_lat, geo_ref_long, 'RX1', 'RX3');
[points_lat3, points_long3] = gen_hyperbola(doa_meters23, rx2_lat, rx2_long, rx3_lat, rx3_long, geo_ref_lat, geo_ref_long, 'RX2', 'RX3');

% figure;
% hold on;
% plot(points_long1, points_lat1, 'r.', 'MarkerSize', 10);
% plot(points_long2, points_lat2, 'g.', 'MarkerSize', 10);
% plot(points_long3, points_lat3, 'b.', 'MarkerSize', 10);
% plot(rx1_long, rx1_lat, 'ro', 'MarkerSize', 10, 'MarkerFaceColor', 'r');
% plot(rx2_long, rx2_lat, 'go', 'MarkerSize', 10, 'MarkerFaceColor', 'g');
% plot(rx3_long, rx3_lat, 'bo', 'MarkerSize', 10, 'MarkerFaceColor', 'b');
% grid on;
% legend('RX1 - RX2', 'RX1 - RX3', 'RX2 - RX3', 'RX1', 'RX2', 'RX3');
% axis equal;
% xlabel('Longitude');
% ylabel('Latitude');
% title(['Hiperbola Plot RX1, RX2, RX3']);
% return;

%% Generate minimum distance
disp(' ');
disp('______________________________________________________________________________________________');
disp('GENERATE MINIMUM DISTANCE');

disp(['poin lat1 = ', num2str(length(points_lat1))]);
disp(['poin lat2 = ', num2str(length(points_lat2))]);
disp(['poin lat3 = ', num2str(length(points_lat3))]);
% Penentuan titik tengah dari perpotongan garis hiperbola RX1 & RX2
for i = 1:length(points_lat1)
    for j = 1:length(points_lat2)
        dist12(i,j) = dist_latlong(points_lat1(i), points_long1(i), points_lat2(j), points_long2(j), geo_ref_lat, geo_ref_long);
    end
end

[min_dist12, min_idx12] = min(dist12(:));
[row_idx12, col_idx12] = ind2sub(size(dist12), min_idx12);
avg_point_lat12 = (points_lat1(row_idx12) + points_lat2(col_idx12)) / 2;
avg_point_long12 = (points_long1(row_idx12) + points_long2(col_idx12)) / 2;
% disp(['avg point lat12', num2str(avg_point_lat12)]);
% disp(['avg point long12', num2str(avg_point_long12)]);

for i = 1:length(points_lat1)
    for j = 1:length(points_lat3)
        dist13(i,j) = dist_latlong(points_lat1(i), points_long1(i), points_lat3(j), points_long3(j), geo_ref_lat, geo_ref_long);
    end
end

[min_dist13, min_idx13] = min(dist13(:));
[row_idx13, col_idx13] = ind2sub(size(dist13), min_idx13);
avg_point_lat13 = (points_lat1(row_idx13) + points_lat3(col_idx13)) / 2;
avg_point_long13 = (points_long1(row_idx13) + points_long3(col_idx13)) / 2;
% disp(['avg point lat13', num2str(avg_point_lat13)]);
% disp(['avg point long13', num2str(avg_point_long13)]);

for i = 1:length(points_lat2)
    for j = 1:length(points_lat3)
        dist23(i,j) = dist_latlong(points_lat2(i), points_long2(i), points_lat3(j), points_long3(j), geo_ref_lat, geo_ref_long);
    end
end

[min_dist23, min_idx23] = min(dist23(:));
[row_idx23, col_idx23] = ind2sub(size(dist23), min_idx23);
avg_point_lat23 = (points_lat2(row_idx23) + points_lat3(col_idx23)) / 2;
avg_point_long23 = (points_long2(row_idx23) + points_long3(col_idx23)) / 2;
% disp(['avg point lat23', num2str(avg_point_lat23)]);
% disp(['avg point long23', num2str(avg_point_long23)]);

avg_point_lat123 = (avg_point_lat12 + avg_point_lat13 + avg_point_lat23) / 3;
avg_point_long123 = (avg_point_long12 + avg_point_long13 + avg_point_long23) / 3;

figure;
hold on;
plot(points_lat1(row_idx12), points_long1(row_idx12), 'r.', 'MarkerSize', 15);
plot(points_lat2(col_idx12), points_long2(col_idx12), 'r.', 'MarkerSize', 15);
plot(avg_point_lat12, avg_point_long12, 'r.', 'MarkerSize', 30);

plot(points_lat1(row_idx13), points_long1(row_idx13), 'g.', 'MarkerSize', 15);
plot(points_lat3(col_idx13), points_long3(col_idx13), 'g.', 'MarkerSize', 15);
plot(avg_point_lat13, avg_point_long13, 'g.', 'MarkerSize', 30);

plot(points_lat2(row_idx23), points_long2(row_idx23), 'b.', 'MarkerSize', 15);
plot(points_lat3(col_idx23), points_long3(col_idx23), 'b.', 'MarkerSize', 15);
plot(avg_point_lat23, avg_point_long23, 'b.', 'MarkerSize', 30);
plot(avg_point_lat123, avg_point_long123, 'k.', 'MarkerSize', 50);
grid on;
legend('point hiperbola1', 'point hiperbola2', 'avg hiperbola12', 'point hiperbola1', 'point hiperbola3', 'avg hiperbola13', 'point hiperbola2', 'point hiperbola3', 'avg hiperbola23', 'avg point all');
axis equal;
xlabel('Longitude');
ylabel('Latitude');
title(['Average Hiperbola Plot RX1, RX2, RX3']);
% return;


disp(' ');
disp('______________________________________________________________________________________________');
disp('GENERATE HTML');
rx_lat_positions  = [rx1_lat   rx2_lat   rx3_lat   tx_cari_lat   tx_ref_lat  geo_ref_lat   avg_point_lat123   center_point_lat    avg_point_lat12   avg_point_lat13   avg_point_lat23];
rx_long_positions = [rx1_long  rx2_long  rx3_long  tx_cari_long  tx_ref_long  geo_ref_long  avg_point_long123  center_point_long  avg_point_long12  avg_point_long13  avg_point_long23];

hyperbola_lat_cell  = {points_lat1,  points_lat2, points_lat3};
hyperbola_long_cell = {points_long1, points_long2, points_long3};

[heatmap_long, heatmap_lat, heatmap_mag, start_lat, stop_lat, start_long, stop_long] = create_heatmap(doa_meters12, doa_meters13, doa_meters23, rx1_lat, rx1_long, rx2_lat, rx2_long, rx3_lat, rx3_long, heatmap_resolution, geo_ref_lat, geo_ref_long); % generate heatmap
heatmap_cell = {heatmap_long, heatmap_lat, heatmap_mag, start_lat, stop_lat, start_long, stop_long};

if strcmp(map_mode, 'google_maps')
    % for google maps
    create_html_file_gm( ['result/map_' file_identifier '_' corr_type '_interp' num2str(interpol_factor) '_bw' int2str(signal_bandwidth_khz) '_smooth' int2str(smoothing_factor) '_gm.html'], rx_lat_positions, rx_long_positions, hyperbola_lat_cell, hyperbola_long_cell, heatmap_cell, heatmap_threshold);
else
    % for open street map
    %create_html_file_osm( ['result/map_' file_identifier '_' corr_type '_interp' num2str(interpol_factor) '_bw' int2str(signal_bandwidth_khz) '_smooth' int2str(smoothing_factor) '_osm.html'], rx_lat_positions, rx_long_positions, hyperbola_lat_cell, hyperbola_long_cell, heatmap_cell, heatmap_threshold);
    create_html_file_osm( [folder_result 'map_' file_identifier '_' corr_type '_interp' num2str(interpol_factor) '_bw' int2str(signal_bandwidth_khz) '_smooth' int2str(smoothing_factor) '_osm.html'], rx_lat_positions, rx_long_positions, hyperbola_lat_cell, hyperbola_long_cell, heatmap_cell, heatmap_threshold);
end
disp('______________________________________________________________________________________________');

end % End of function evaluation_main
