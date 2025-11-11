% filepath: run_batch_evaluation.m
% Script untuk menjalankan evaluation_main 30 kali dengan file berbeda
% Pattern: "933_1031_2025_6_12_9_" + number + ".dat"

clc;
clear;

% Konfigurasi
base_filename = '1000_980_2025_7_31_';
hour = 10; % Jam awal
separate_hour_minute = '_';
menit = 46;
file_extension = '.dat';
num_runs = 30;

% Array untuk menyimpan hasil atau log
results = cell(num_runs, 1);
success_count = 0;
failed_files = {};

fprintf('=== Batch Evaluation Started ===\n');
fprintf('Running evaluation_main for %d files...\n\n', num_runs);

% Loop untuk setiap file
for i = 1:num_runs
    % Buat nama file
    filename = [base_filename num2str(hour) separate_hour_minute num2str(menit) file_extension];
    
    fprintf('[%d/%d] Processing: %s\n', i, num_runs, filename);
    
    try
        % Jalankan evaluation_main
        tic; % Start timer
        
        elapsed_time = toc; % Stop timer
        evaluation_main(filename);
        
        results{i} = sprintf('SUCCESS - Time: %.2f seconds', elapsed_time);
        success_count = success_count + 1;
        
        fprintf('  ✓ Completed in %.2f seconds\n', elapsed_time);
        
    catch ME
        fprintf('  ✗ Error: %s\n', ME.message);
        failed_files{end+1} = filename; % Store failed file
    end
    
    fprintf('\n');
    menit = menit + 1; % Increment menit for next file
    if (menit == 60)
        hour = hour + 1; % Increment hour if menit reaches 60
        menit = 0; % Reset menit to 0
    end
end

% Summary
fprintf('=== Batch Evaluation Completed ===\n');
fprintf('Total files processed: %d\n', num_runs);
fprintf('Successful: %d\n', success_count);
fprintf('Failed: %d\n', length(failed_files));

if ~isempty(failed_files)
    fprintf('\nFailed files:\n');
    for i = 1:length(failed_files)
        fprintf('  - %s\n', failed_files{i});
    end
end

fprintf('\nBatch evaluation finished!\n');