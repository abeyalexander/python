import numpy as np
import matplotlib.pyplot as plt
from scipy import signal, misc
import scipy.interpolate
import scipy.io.wavfile as audio
import math
import binascii

def generate_ofdm_data_from_64_data_block(data_block):
	global CP, K, pilotValue, P, allCarriers, pilotCarriers, dataCarriers, mu
	global demapping_table, bits, channelResponse, SNRdb
	
	def SP(bits):
		return bits.reshape((len(dataCarriers), mu))

	def Mapping(bits):
		return np.array([mapping_table[tuple(b)] for b in bits])

	def OFDM_symbol(QAM_payload):
		symbol = np.zeros(K, dtype=complex) # the overall K subcarriers
		symbol[pilotCarriers] = pilotValue  # allocate the pilot subcarriers 
		symbol[dataCarriers] = QAM_payload  # allocate the pilot subcarriers
		return symbol      

	def IDFT(OFDM_data):
		return np.fft.ifft(OFDM_data)

	def addCP(OFDM_time):
		cp = OFDM_time[-CP:]               # take the last CP samples ...
		return np.hstack([cp, OFDM_time])  # ... and add them to the beginning

	def channel(signal):
		convolved = np.convolve(signal, channelResponse)
		signal_power = np.mean(abs(convolved**2))
		sigma2 = signal_power * 10**(-SNRdb/10)  # calculate noise power based on signal power and SNR

		#print ("RX Signal power: %.4f. Noise power: %.4f" % (signal_power, sigma2))

		# Generate complex noise with given variance
		noise = np.sqrt(sigma2/2) * (np.random.randn(*convolved.shape)+1j*np.random.randn(*convolved.shape))
		return convolved + noise
	
	K = 64 # number of OFDM subcarriers
	CP = K//4  # length of the cyclic prefix: 25% of the block
	P = 8 # number of pilot carriers per OFDM block
	pilotValue = 3+3j # The known value each pilot transmits
	allCarriers = np.arange(K)  # indices of all subcarriers ([0, 1, ... K-1])

	pilotCarriers = allCarriers[::K//P] # Pilots is every (K/P)th carrier.

	# For convenience of channel estimation, let's make the last carriers also be a pilot
	pilotCarriers = np.hstack([pilotCarriers, np.array([allCarriers[-1]])])
	P = P+1

	# data carriers are all remaining carriers
	dataCarriers = np.delete(allCarriers, pilotCarriers)

	#print ("allCarriers:   %s" % allCarriers)
	#print ("pilotCarriers: %s" % pilotCarriers)
	#print ("dataCarriers:  %s" % dataCarriers)
	#plt.plot(pilotCarriers, np.zeros_like(pilotCarriers), 'bo', label='pilot')
	#plt.plot(dataCarriers, np.zeros_like(dataCarriers), 'ro', label='data')
	#plt.show()

	mu = 4 # bits per symbol (i.e. 16QAM)
	payloadBits_per_OFDM = len(dataCarriers)*mu  # number of payload bits per OFDM symbol

	mapping_table = {
		(0,0,0,0) : -3-3j,
		(0,0,0,1) : -3-1j,
		(0,0,1,0) : -3+3j,
		(0,0,1,1) : -3+1j,
		(0,1,0,0) : -1-3j,
		(0,1,0,1) : -1-1j,
		(0,1,1,0) : -1+3j,
		(0,1,1,1) : -1+1j,
		(1,0,0,0) :  3-3j,
		(1,0,0,1) :  3-1j,
		(1,0,1,0) :  3+3j,
		(1,0,1,1) :  3+1j,
		(1,1,0,0) :  1-3j,
		(1,1,0,1) :  1-1j,
		(1,1,1,0) :  1+3j,
		(1,1,1,1) :  1+1j
	}
	'''
	for b3 in [0, 1]:
		for b2 in [0, 1]:
			for b1 in [0, 1]:
				for b0 in [0, 1]:
					B = (b3, b2, b1, b0)
					Q = mapping_table[B]
					plt.plot(Q.real, Q.imag, 'bo')
					plt.text(Q.real, Q.imag+0.2, "".join(str(x) for x in B), ha='center')
	'''
	#plt.show()
	demapping_table = {v : k for k, v in mapping_table.items()}
	channelResponse = np.array([1, 0, 0.3+0.3j])  # the impulse response of the wireless channel
	H_exact = np.fft.fft(channelResponse, K)
	#plt.plot(allCarriers, abs(H_exact))

	SNRdb = 25  # signal to noise-ratio in dB at the receiver
	#plt.show()

	#section receiver 4th part

	#bits = np.random.binomial(n=1, p=0.5, size=(payloadBits_per_OFDM, ))
	bits = data_block
	#print ("Bits count: ", len(bits))
	#print ("First 20 bits: ", bits[:20])
	#print ("Mean of bits (should be around 0.5): ", np.mean(bits))

	bits_SP = SP(bits)
	#print ("First 5 bit groups")
	#print (bits_SP[:5,:])

	QAM = Mapping(bits_SP)
	#print ("First 5 QAM symbols and bits:")
	#print (bits_SP[:5,:])
	#print (QAM[:5])

	OFDM_data = OFDM_symbol(QAM)
	#print ("Number of OFDM carriers in frequency domain: ", len(OFDM_data))

	OFDM_time = IDFT(OFDM_data)
	#print ("Number of OFDM samples in time-domain before CP: ", len(OFDM_time))

	OFDM_withCP = addCP(OFDM_time)
	#print ("Number of OFDM samples in time domain with CP: ", len(OFDM_withCP))

	OFDM_TX = OFDM_withCP
	return OFDM_TX

def convert_ofdm_data_to_quad_data(ofdm_data):
	global Fs, fc, Ts, BN, t_u

	Fs = int(44100)    # the sampling frequency we use for the discrete simulation of analog signals

	fc = int(3e3)
	Ts = 1e-3        # 1 ms symbol spacing, i.e. the baseband samples are Ts seconds apart.
	BN = 1/(2*Ts )   # the Nyquist bandwidth of the baseband signal.
	
	t_u = np.arange(len(ofdm_data))/Fs
	tx_i = ofdm_data.real
	tx_q = ofdm_data.imag

	tx_iup = tx_i * np.cos(2*np.pi*t_u*fc)  
	tx_qup = tx_q * -np.sin(2*np.pi*t_u*fc)

	quad_ofdm_data = tx_iup + tx_qup
	return quad_ofdm_data

def convert_data_to_audio(data, file_name):
    #print(data)
    #data = np.random.uniform(-1,1,44100) # 44100 random samples between -1 and 1
    scaled = np.int16(data/np.max(np.abs(data)) * 32767)
    audio.write(file_name+".wav", 44100, scaled)


def read_audio_to_data_array(filename):
	sample_rate, samples = audio.read(filename+".wav")
	return samples

def channel(signal):
	global channelResponse, SNRdb
	convolved = np.convolve(signal, channelResponse)
	signal_power = np.mean(abs(convolved**2))
	sigma2 = signal_power * 10**(-SNRdb/10)  # calculate noise power based on signal power and SNR

	print ("RX Signal power: %.4f. Noise power: %.4f" % (signal_power, sigma2))

	# Generate complex noise with given variance
	noise = np.sqrt(sigma2/2) * (np.random.randn(*convolved.shape)+1j*np.random.randn(*convolved.shape))
	return convolved + noise

def rx_data_to_quad_data(rx_data):
	global Fs, fc, Ts, BN, t_u
	s = rx_data
	idown = s * np.cos(2*np.pi*-fc*t_u) 
	qdown = s * -np.sin(2*np.pi*fc*t_u)
	cutoff = 5*BN        # arbitrary design parameters
	lowpass_order = 51   
	lowpass_delay = (lowpass_order // 2)/Fs  # a lowpass of order N delays the signal by N/2 samples (see plot)
	# design the filter
	lowpass = scipy.signal.firwin(lowpass_order, cutoff/(Fs/2))
	idown_lp = scipy.signal.lfilter(lowpass, 1, idown)
	qdown_lp = scipy.signal.lfilter(lowpass, 1, qdown)
	v = idown_lp + 1j*qdown_lp
	return (v)

def removeCP(signal):
	global CP, K
	return signal[CP:(CP+K)]

def DFT(OFDM_RX):
    return np.fft.fft(OFDM_RX)

def channelEstimate(OFDM_demod):
	global pilotCarriers, pilotValue
	pilots = OFDM_demod[pilotCarriers]  # extract the pilot values from the RX signal
	Hest_at_pilots = pilots / pilotValue # divide by the transmitted pilot values

	# Perform interpolation between the pilot carriers to get an estimate
	# of the channel in the data carriers. Here, we interpolate absolute value and phase 
	# separately
	Hest_abs = scipy.interpolate.interp1d(pilotCarriers, abs(Hest_at_pilots), kind='linear')(allCarriers)
	Hest_phase = scipy.interpolate.interp1d(pilotCarriers, np.angle(Hest_at_pilots), kind='linear')(allCarriers)
	Hest = Hest_abs * np.exp(1j*Hest_phase)

	#plt.plot(allCarriers, abs(H_exact), label='Correct Channel')
	#plt.stem(pilotCarriers, abs(Hest_at_pilots), label='Pilot estimates')
	#plt.plot(allCarriers, abs(Hest), label='Estimated channel via interpolation')
	#plt.grid(True); plt.xlabel('Carrier index'); plt.ylabel('$|H(f)|$'); plt.legend(fontsize=10)
	#plt.ylim(0,2)

	return Hest

def equalize(OFDM_demod, Hest):
    return OFDM_demod / Hest

def get_payload(equalized):
    return equalized[dataCarriers]

def Demapping(QAM):
	global demapping_table
	# array of possible constellation points
	constellation = np.array([x for x in demapping_table.keys()])

	# calculate distance of each RX point to each possible point
	dists = abs(QAM.reshape((-1,1)) - constellation.reshape((1,-1)))

	# for each element in QAM, choose the index in constellation 
	# that belongs to the nearest constellation point
	const_index = dists.argmin(axis=1)

	# get back the real constellation point
	hardDecision = constellation[const_index]

	# transform the constellation point into the bit groups
	return np.vstack([demapping_table[C] for C in hardDecision]), hardDecision

def PS(bits):
    return bits.reshape((-1,))

def combine_complex_data_to_sequenced_real_data(complex_data):
	sequenced_real_complex_data = []
	for i in complex_data:
		sequenced_real_complex_data.append(i.real)
		sequenced_real_complex_data.append(i.imag)
	return sequenced_real_complex_data

def split_sequenced_real_data_to_complex_data(sequenced_real_complex_data):
	real_data = np.array(sequenced_real_complex_data[0:len(sequenced_real_complex_data):2])
	imag_data = np.array(sequenced_real_complex_data[1:len(sequenced_real_complex_data):2])
	complex_data = real_data+1j*imag_data
	return complex_data


def adjust_string_length(string_data,len_adj):
	len_data = len(string_data)
	len_appended_data = len_adj*math.ceil(len_data/len_adj)
	appended_string_data = string_data.ljust(len_appended_data, '0')
	return appended_string_data


def convert_file_to_binary_string(filepath):
	#filepath = "mysong.mp3"
	file = open(filepath, "rb")
	with file:
		byte = file.read()
		hexadecimal = binascii.hexlify(byte)
		decimal = int(hexadecimal, 16)
		binary = bin(decimal)[2:].zfill(16)
		return binary

def convert_array_data_to_binary_string(data_array):
	bin_data = ""
	for data in data_array:
		hexadecimal = binascii.hexlify(data)
		decimal = int(hexadecimal, 16)
		binary = bin(decimal)[2:].zfill(16)
		bin_data  = bin_data + binary
	return bin_data

def binary_string_to_numeric_array(binary_string):
	numeric_array = []
	char_array = list(binary_string)
	for char_element in char_array:
		numeric_array.append(int(char_element))
	return numeric_array

f_name = "/media/abraham/Windows/Users/abraham/Documents/My Music/ofdm_audio/ofdm_audio"
len_adj = 220
#data_blocks = np.random.binomial(n=1, p=0.5, size=(220*n_blocks, ))
data_blocks = np.random.binomial(n=1, p=0.5, size=(10, ))

audio_data = read_audio_to_data_array(f_name)
binary_data_string = convert_array_data_to_binary_string(audio_data)

binary_data_string_len_adjusted = adjust_string_length(binary_data_string,len_adj)

data_blocks = np.asarray(binary_string_to_numeric_array(binary_data_string_len_adjusted))

n_blocks = 1#int(len(data_blocks)/len_adj)

output = []
for i in range(n_blocks):
    data_block = data_blocks[i*220:(i*220)+220]
    output = np.concatenate([output,generate_ofdm_data_from_64_data_block(data_block)])
    print(i)

f_name = "/media/abraham/Windows/Users/abraham/Documents/My Music/ofdm_audio/ofdm_audio"
tx_data = combine_complex_data_to_sequenced_real_data(output) 

convert_data_to_audio(tx_data,f_name) 

 
audio_data = read_audio_to_data_array(f_name)

rx_data = channel(audio_data)

ofdm_rx_data = split_sequenced_real_data_to_complex_data(rx_data)

OFDM_RX = ofdm_rx_data

OFDM_RX_noCP = removeCP(OFDM_RX)

OFDM_demod = DFT(OFDM_RX_noCP)

Hest = channelEstimate(OFDM_demod)

equalized_Hest = equalize(OFDM_demod, Hest)

QAM_est = get_payload(equalized_Hest)

PS_est, hardDecision = Demapping(QAM_est)

for qam, hard in zip(QAM_est, hardDecision):
    plt.plot([qam.real, hard.real], [qam.imag, hard.imag], 'b-o');
    plt.plot(hardDecision.real, hardDecision.imag, 'ro')
plt.show()

bits_est = PS(PS_est)

print ("Obtained Bit error rate: ", np.sum(abs(bits-bits_est))/len(bits))
